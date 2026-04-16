import json
import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from together import Together

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
MODEL_ID = "meta-llama/Llama-3-70b-chat-hf"
FALLBACK_MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
ITUNES_HEADERS = {"User-Agent": "SongRecommender/1.0"}

app = FastAPI(title="Song Recommender")


def get_client() -> Together:
    key = os.getenv("TOGETHER_API_KEY")
    if not key:
        raise HTTPException(
            status_code=500,
            detail="TOGETHER_API_KEY is not set. Add it to your .env file.",
        )
    return Together(api_key=key)


def parse_song_json(raw: str) -> list[dict]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("Response must be a JSON array")
    return data


def normalize_song_item(item: dict) -> dict:
    return {
        "title": str(item.get("title", "Unknown")),
        "artist": str(item.get("artist", "Unknown")),
        "why": str(item.get("why", "")),
    }


def track_key(title: str, artist: str) -> tuple[str, str]:
    return (title.strip().lower(), artist.strip().lower())


def is_duplicate_song(
    song: dict,
    *,
    replace_title: str,
    replace_artist: str,
    other_keys: set[tuple[str, str]],
) -> bool:
    k = track_key(song["title"], song["artist"])
    if k == track_key(replace_title, replace_artist):
        return True
    return k in other_keys


def request_recommendations(client: Together, messages: list[dict]) -> str:
    models_to_try = [MODEL_ID, FALLBACK_MODEL_ID]
    errors = []

    for model_name in models_to_try:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
            )
            content = response.choices[0].message.content
            if content:
                return content
            errors.append(f"{model_name}: empty response")
        except Exception as e:
            errors.append(f"{model_name}: {e!s}")

    raise HTTPException(
        status_code=502,
        detail="Together API request failed for all models. " + " | ".join(errors),
    )


class RecommendRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
        description="What the user wants (mood, genre, similar artists, etc.)",
    )


class SongRef(BaseModel):
    title: str = ""
    artist: str = ""


class ReplaceSongRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    replace: SongRef
    others: list[SongRef] = Field(default_factory=list)


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html")


@app.get("/api/preview")
async def preview(
    title: str = Query(default="", max_length=220),
    artist: str = Query(default="", max_length=220),
) -> dict:
    """Return an iTunes ~30s preview URL for the track (Apple Search API, no API key)."""
    t = title.strip()
    a = artist.strip()
    if not t and not a:
        raise HTTPException(
            status_code=400,
            detail="Provide at least a title or artist.",
        )
    term = f"{a} {t}".strip()
    params = {
        "term": term,
        "media": "music",
        "entity": "song",
        "limit": "25",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                ITUNES_SEARCH_URL,
                params=params,
                headers=ITUNES_HEADERS,
            )
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach iTunes lookup: {e!s}",
        ) from e
    data = r.json()
    for track in data.get("results", []):
        url = track.get("previewUrl")
        if isinstance(url, str) and url.startswith("http"):
            return {"preview_url": url}
    raise HTTPException(
        status_code=404,
        detail="No preview audio found for this track.",
    )


@app.post("/api/recommend")
async def recommend(body: RecommendRequest) -> dict:
    client = get_client()
    system = (
        "You are a music expert. Reply with ONLY valid JSON, no markdown or explanation. "
        "Return a JSON array of exactly 8 objects. Each object must have: "
        '"title" (string), "artist" (string), "why" (one short sentence explaining the pick). '
        "Choose real, well-known songs that fit the user's request."
    )
    user = f"Song recommendations for: {body.prompt}"

    parse_errors = []
    songs = None
    base_messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    for attempt in range(3):
        messages = list(base_messages)
        if attempt > 0:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous reply was not valid JSON. "
                        "Reply again with ONLY a valid JSON array and no extra text."
                    ),
                }
            )

        content = request_recommendations(client, messages)
        try:
            songs = parse_song_json(content)
            break
        except (json.JSONDecodeError, ValueError) as e:
            parse_errors.append(str(e))

    if songs is None:
        raise HTTPException(
            status_code=502,
            detail="Could not parse model output as JSON after retries: "
            + " | ".join(parse_errors),
        )

    normalized = []
    for item in songs:
        if not isinstance(item, dict):
            continue
        normalized.append(normalize_song_item(item))

    return {"songs": normalized}


@app.post("/api/recommend/one")
async def recommend_one(body: ReplaceSongRequest) -> dict:
    client = get_client()
    other_keys: set[tuple[str, str]] = {
        track_key(o.title, o.artist) for o in body.others if o.title or o.artist
    }
    avoid_lines = []
    for o in body.others:
        if o.title.strip() or o.artist.strip():
            avoid_lines.append(f'- "{o.title}" by {o.artist}')
    avoid_block = (
        "\nDo not suggest any of these songs that are already on the playlist:\n"
        + "\n".join(avoid_lines)
        if avoid_lines
        else ""
    )
    system = (
        "You are a music expert. Reply with ONLY valid JSON, no markdown or explanation. "
        "Return a JSON array containing exactly 1 object. The object must have: "
        '"title" (string), "artist" (string), "why" (one short sentence explaining the pick). '
        "Choose a real, well-known song that fits the user's request."
    )
    user = (
        f"Playlist request: {body.prompt}\n\n"
        f'The user wants a different song instead of "{body.replace.title}" by '
        f"{body.replace.artist}. Suggest one new song that still fits the same request.\n"
        f'Do not suggest "{body.replace.title}" by {body.replace.artist} again.'
        f"{avoid_block}"
    )

    parse_errors: list[str] = []
    duplicate_retries = 0
    max_duplicate_retries = 3
    song_out: dict | None = None

    while duplicate_retries <= max_duplicate_retries:
        base_messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        if duplicate_retries > 0:
            base_messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your suggestion duplicated a song you were asked to avoid. "
                        "Reply again with ONLY a JSON array of one object, picking a "
                        "different real song."
                    ),
                }
            )

        songs: list[dict] | None = None
        for attempt in range(3):
            messages = list(base_messages)
            if attempt > 0:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your previous reply was not valid JSON. "
                            "Reply again with ONLY a valid JSON array of one object."
                        ),
                    }
                )

            content = request_recommendations(client, messages)
            try:
                parsed = parse_song_json(content)
                if not parsed or not isinstance(parsed[0], dict):
                    raise ValueError("Expected a non-empty JSON array")
                songs = [normalize_song_item(parsed[0])]
                break
            except (json.JSONDecodeError, ValueError) as e:
                parse_errors.append(str(e))

        if songs is None:
            raise HTTPException(
                status_code=502,
                detail="Could not parse model output as JSON after retries: "
                + " | ".join(parse_errors),
            )

        candidate = songs[0]
        if is_duplicate_song(
            candidate,
            replace_title=body.replace.title,
            replace_artist=body.replace.artist,
            other_keys=other_keys,
        ):
            duplicate_retries += 1
            parse_errors = []
            continue

        song_out = candidate
        break

    if song_out is None:
        raise HTTPException(
            status_code=502,
            detail="Could not find a different song after several tries; try again.",
        )

    return {"song": song_out}
