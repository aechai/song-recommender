import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from together import Together

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
MODEL_ID = "meta-llama/Llama-3-70b-chat-hf"
FALLBACK_MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
RECOMMEND_COUNT = 20
QUIZ_SONG_COUNT = 20
ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
ITUNES_HEADERS = {"User-Agent": "SongRecommender/1.0"}

app = FastAPI(title="Song Recommender")

SESSION_COOKIE = "sr_session"
_oauth_states: dict[str, str] = {}
_google_tokens: dict[str, dict[str, Any]] = {}


def _now() -> int:
    return int(time.time())


def _env_required(var: str) -> str:
    v = os.getenv(var, "").strip()
    if not v:
        raise HTTPException(status_code=500, detail=f"{var} is not set in .env")
    return v


def _get_or_set_session_id(request: Request, response: JSONResponse | RedirectResponse | None = None) -> str:
    sid = request.cookies.get(SESSION_COOKIE, "").strip()
    if sid:
        return sid
    sid = secrets.token_urlsafe(24)
    if response is not None:
        response.set_cookie(
            key=SESSION_COOKIE,
            value=sid,
            httponly=True,
            samesite="lax",
        )
    return sid


def _token_is_valid(tok: dict[str, Any]) -> bool:
    try:
        return bool(tok.get("access_token")) and int(tok.get("expires_at", 0)) - _now() > 30
    except Exception:
        return False


async def _refresh_access_token(refresh_token: str) -> dict[str, Any]:
    client_id = _env_required("GOOGLE_CLIENT_ID")
    client_secret = _env_required("GOOGLE_CLIENT_SECRET")
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(token_url, data=data)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Google token refresh failed: {r.text}")
    payload = r.json()
    access_token = payload.get("access_token")
    expires_in = int(payload.get("expires_in") or 3600)
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(status_code=502, detail="Google token refresh did not return access_token.")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": _now() + max(60, expires_in),
        "scope": payload.get("scope", ""),
        "token_type": payload.get("token_type", "Bearer"),
    }


async def _get_access_token_for_request(request: Request) -> str:
    sid = request.cookies.get(SESSION_COOKIE, "").strip()
    if not sid:
        raise HTTPException(status_code=401, detail="Not linked. Open Account to link Google.")
    tok = _google_tokens.get(sid)
    if not tok:
        raise HTTPException(status_code=401, detail="Not linked. Open Account to link Google.")
    if _token_is_valid(tok):
        return str(tok["access_token"])
    refresh_token = tok.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise HTTPException(status_code=401, detail="Link expired (no refresh token). Link Google again.")
    new_tok = await _refresh_access_token(refresh_token)
    _google_tokens[sid] = new_tok
    return str(new_tok["access_token"])


def get_client() -> Together:
    key = os.getenv("TOGETHER_API_KEY")
    if not key:
        raise HTTPException(
            status_code=500,
            detail="TOGETHER_API_KEY is not set. Add it to your .env file.",
        )
    return Together(api_key=key)


def _strip_code_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text


def parse_song_json(raw: str) -> list[dict]:
    data = json.loads(_strip_code_fence(raw))
    if not isinstance(data, list):
        raise ValueError("Response must be a JSON array")
    return data


def _extract_quiz_persona(obj: dict) -> str:
    for key in ("persona", "musical_persona", "musicalPersona", "musical_persona_name", "name"):
        v = obj.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _songs_key_from_obj(obj: dict) -> list | None:
    for key in ("songs", "tracks", "recommendations", "results", "picks"):
        v = obj.get(key)
        if isinstance(v, list) and v:
            return v
    return None


def parse_quiz_response_json(raw: str) -> tuple[str, list[dict]]:
    """Quiz returns JSON object {{persona, songs}} or a bare array of songs."""
    data = json.loads(_strip_code_fence(raw))
    if isinstance(data, list):
        if not data:
            raise ValueError("Quiz response was an empty list")
        return "Your musical persona", data
    if not isinstance(data, dict):
        raise ValueError("Quiz response must be a JSON object or array")

    persona = _extract_quiz_persona(data)
    songs = _songs_key_from_obj(data)
    if not isinstance(songs, list) or not songs:
        raise ValueError("Quiz response must include a non-empty songs array (or a top-level array)")
    if not persona:
        persona = "Your musical persona"
    return persona, songs


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


def request_recommendations(
    client: Together,
    messages: list[dict],
    *,
    max_tokens: int = 2048,
) -> str:
    models_to_try = [MODEL_ID, FALLBACK_MODEL_ID]
    errors = []

    for model_name in models_to_try:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=max_tokens,
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


class SongRef(BaseModel):
    title: str = ""
    artist: str = ""


class RecommendRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
        description="What the user wants (mood, genre, similar artists, etc.)",
    )
    count: int = Field(
        default=8,
        ge=1,
        le=20,
        description="How many songs to recommend (1-20).",
    )
    favorites: list[SongRef] = Field(
        default_factory=list,
        description="Optional saved tracks to steer taste (title + artist).",
    )


class ReplaceSongRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    replace: SongRef
    others: list[SongRef] = Field(default_factory=list)
    favorites: list[SongRef] = Field(
        default_factory=list,
        description="Optional saved tracks to steer taste when replacing one pick.",
    )


class SimilarFromTrackRequest(BaseModel):
    seed: SongRef
    seed_why: str = Field(
        default="",
        max_length=2000,
        description="Optional 'why' text from the current card for the seed track.",
    )
    context_prompt: str = Field(
        default="",
        max_length=4000,
        description="Optional original user request for extra context.",
    )
    favorites: list[SongRef] = Field(
        default_factory=list,
        description="Optional saved tracks to steer taste.",
    )


class YouTubeTrack(BaseModel):
    title: str = Field(default="", max_length=220)
    artist: str = Field(default="", max_length=220)


class YouTubeExportRequest(BaseModel):
    name: str = Field(default="Song Recommender playlist", max_length=120)
    tracks: list[YouTubeTrack] = Field(default_factory=list, max_length=80)


def _trim_favorites(favs: list[SongRef], *, limit: int = 40) -> list[SongRef]:
    out = [f for f in favs[:limit] if f.title.strip() or f.artist.strip()]
    return out


def favorites_context_block(favs: list[SongRef]) -> str:
    lines = [f'- "{f.title.strip()}" by {f.artist.strip()}' for f in favs]
    if not lines:
        return ""
    return (
        "\n\nThe user saved these favorite tracks (infer genres, moods, eras, and similar artists):"
        "\n"
        + "\n".join(lines)
        + "\n\nUse them as taste signals. Your picks must fit the request above and align with this profile. "
        "Do not output the exact same title+artist as any favorite listed above unless the user explicitly "
        "asked for those tracks."
    )


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html")


@app.get("/favorites")
async def serve_favorites() -> FileResponse:
    return FileResponse(BASE_DIR / "favorites.html")


@app.get("/playlists")
async def serve_playlists() -> FileResponse:
    return FileResponse(BASE_DIR / "playlists.html")


@app.get("/personality-quiz")
async def serve_personality_quiz() -> FileResponse:
    return FileResponse(BASE_DIR / "personality-quiz.html")


@app.get("/account")
async def serve_account() -> FileResponse:
    return FileResponse(BASE_DIR / "account.html")


@app.get("/api/account/status")
async def account_status(request: Request) -> JSONResponse:
    sid = request.cookies.get(SESSION_COOKIE, "").strip()
    linked = bool(sid and sid in _google_tokens)
    resp = JSONResponse({"linked": linked})
    if not sid:
        _get_or_set_session_id(request, resp)
    return resp


@app.get("/auth/google/start")
async def auth_google_start(request: Request) -> RedirectResponse:
    client_id = _env_required("GOOGLE_CLIENT_ID")
    redirect_uri = _env_required("GOOGLE_REDIRECT_URI")
    state = secrets.token_urlsafe(18)

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    scope = "https://www.googleapis.com/auth/youtube"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }

    resp = RedirectResponse(url=str(httpx.URL(auth_url, params=params)))
    sid = _get_or_set_session_id(request, resp)
    _oauth_states[sid] = state
    return resp


@app.get("/auth/google/callback")
async def auth_google_callback(request: Request, code: str = Query(default=""), state: str = Query(default="")) -> RedirectResponse:
    if not code:
        raise HTTPException(status_code=400, detail="Missing code.")
    resp = RedirectResponse(url="/account")
    sid = _get_or_set_session_id(request, resp)
    expected = _oauth_states.get(sid)
    if not expected or not state or state != expected:
        raise HTTPException(status_code=400, detail="Invalid OAuth state. Try linking again.")

    client_id = _env_required("GOOGLE_CLIENT_ID")
    client_secret = _env_required("GOOGLE_CLIENT_SECRET")
    redirect_uri = _env_required("GOOGLE_REDIRECT_URI")
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(token_url, data=data)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Google token exchange failed: {r.text}")
    payload = r.json()
    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    expires_in = int(payload.get("expires_in") or 3600)
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(status_code=502, detail="Google token exchange did not return access_token.")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise HTTPException(status_code=502, detail="Google token exchange did not return refresh_token. Try linking again.")

    _google_tokens[sid] = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": _now() + max(60, expires_in),
        "scope": payload.get("scope", ""),
        "token_type": payload.get("token_type", "Bearer"),
    }
    _oauth_states.pop(sid, None)
    return resp


@app.post("/auth/google/unlink")
async def auth_google_unlink(request: Request) -> JSONResponse:
    resp = JSONResponse({"ok": True})
    sid = _get_or_set_session_id(request, resp)
    _google_tokens.pop(sid, None)
    _oauth_states.pop(sid, None)
    return resp


async def _yt_api_request(
    *,
    method: str,
    url: str,
    access_token: str,
    params: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=25.0) as client:
        r = await client.request(method, url, headers=headers, params=params, json=json_body)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"YouTube API error ({r.status_code}): {r.text}")
    data = r.json()
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="YouTube API returned non-object JSON.")
    return data


def _yt_search_query(title: str, artist: str) -> str:
    t = title.strip()
    a = artist.strip()
    if t and a:
        return f"\"{t}\" {a}"
    return t or a


@app.post("/api/youtube/export")
async def youtube_export(request: Request, body: YouTubeExportRequest) -> dict:
    if not body.tracks:
        raise HTTPException(status_code=400, detail="No tracks provided.")
    access_token = await _get_access_token_for_request(request)

    create_url = "https://www.googleapis.com/youtube/v3/playlists"
    playlist = await _yt_api_request(
        method="POST",
        url=create_url,
        access_token=access_token,
        params={"part": "snippet,status"},
        json_body={
            "snippet": {"title": body.name.strip() or "Song Recommender playlist"},
            "status": {"privacyStatus": "private"},
        },
    )
    playlist_id = playlist.get("id")
    if not isinstance(playlist_id, str) or not playlist_id:
        raise HTTPException(status_code=502, detail="YouTube did not return a playlist id.")

    skipped: list[dict[str, str]] = []
    added = 0

    for tr in body.tracks[:80]:
        q = _yt_search_query(tr.title, tr.artist)
        if not q.strip():
            skipped.append({"title": tr.title, "artist": tr.artist, "reason": "Empty title/artist"})
            continue

        search_url = "https://www.googleapis.com/youtube/v3/search"
        search = await _yt_api_request(
            method="GET",
            url=search_url,
            access_token=access_token,
            params={
                "part": "snippet",
                "type": "video",
                "maxResults": "1",
                "q": q,
            },
        )
        items = search.get("items", [])
        if not isinstance(items, list) or not items:
            skipped.append({"title": tr.title, "artist": tr.artist, "reason": "No YouTube match"})
            continue
        first = items[0]
        if not isinstance(first, dict):
            skipped.append({"title": tr.title, "artist": tr.artist, "reason": "Bad search item"})
            continue
        id_obj = first.get("id", {})
        video_id = id_obj.get("videoId") if isinstance(id_obj, dict) else None
        if not isinstance(video_id, str) or not video_id:
            skipped.append({"title": tr.title, "artist": tr.artist, "reason": "No videoId"})
            continue

        insert_url = "https://www.googleapis.com/youtube/v3/playlistItems"
        await _yt_api_request(
            method="POST",
            url=insert_url,
            access_token=access_token,
            params={"part": "snippet"},
            json_body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        )
        added += 1

    return {
        "playlistId": playlist_id,
        "playlistUrl": f"https://www.youtube.com/playlist?list={playlist_id}",
        "addedCount": added,
        "skipped": skipped,
    }


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
    n = int(body.count or 8)
    client = get_client()
    favs = _trim_favorites(body.favorites)
    user = f"Song recommendations for: {body.prompt}"
    if favs:
        user += favorites_context_block(favs)

    quiz = body.prompt.strip().startswith("Quiz Results:")

    if quiz:
        system = (
            "You are a music expert. Reply with ONLY valid JSON, no markdown or explanation. "
            f'The user completed a "Musical Personality Quiz." Their answers begin with the prefix "Quiz Results:". '
            f"1) Invent a short, memorable musical persona name (2–5 words) that fits their style, e.g. "
            f"\"The Melancholic Explorer\". Use the JSON key \"persona\" (string) for that name. "
            f"2) Recommend exactly {QUIZ_SONG_COUNT} real, well-known songs that fit that persona. "
            f"Each item in the songs array must have: "
            f'"title" (string), "artist" (string), "why" (one short sentence: why it fits the persona). '
            f"Output a single JSON object with exactly two keys: \"persona\" and \"songs\". "
            f'"songs" must be an array of exactly {QUIZ_SONG_COUNT} objects.'
        )
    else:
        system = (
            "You are a music expert. Reply with ONLY valid JSON, no markdown or explanation. "
            f"Return a JSON array of exactly {n} objects. Each object must have: "
            '"title" (string), "artist" (string), "why" (one short sentence explaining the pick). '
            "Choose real, well-known songs that fit the user's request."
        )

    parse_errors: list[str] = []
    songs: list[dict] | None = None
    persona: str | None = None
    max_tokens = 4096 if quiz else 2048
    base_messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    for attempt in range(3):
        messages = list(base_messages)
        if attempt > 0:
            if quiz:
                fix = (
                    "Your previous reply was not valid JSON. Reply again with ONLY one JSON object with keys "
                    f'"persona" (string) and "songs" (array of exactly {QUIZ_SONG_COUNT} objects with title, artist, why).'
                )
            else:
                fix = (
                    "Your previous reply was not valid JSON. Reply again with ONLY a valid JSON array "
                    f"of exactly {n} objects and no extra text."
                )
            messages.append({"role": "user", "content": fix})

        content = request_recommendations(client, messages, max_tokens=max_tokens)
        try:
            if quiz:
                persona, raw = parse_quiz_response_json(content)
                songs = raw
            else:
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

    if quiz:
        normalized = normalized[:QUIZ_SONG_COUNT]
        if len(normalized) < QUIZ_SONG_COUNT:
            raise HTTPException(
                status_code=502,
                detail=f"Model returned {len(normalized)} songs; expected {QUIZ_SONG_COUNT}. Try again.",
            )
        return {
            "songs": normalized,
            "persona": persona or "Your musical persona",
        }
    if len(normalized) < n:
        raise HTTPException(
            status_code=502,
            detail=f"Model returned {len(normalized)} songs; expected {n}. Try again.",
        )
    return {"songs": normalized[:n]}


@app.post("/api/recommend/similar")
async def recommend_similar(body: SimilarFromTrackRequest) -> dict:
    st = body.seed.title.strip()
    sa = body.seed.artist.strip()
    if not st and not sa:
        raise HTTPException(
            status_code=400,
            detail="Seed track must include a title or artist.",
        )

    client = get_client()
    seed_key = track_key(st, sa)
    seed_norm = normalize_song_item(
        {
            "title": st or "Unknown",
            "artist": sa or "Unknown",
            "why": body.seed_why.strip() or "Your selected track.",
        }
    )

    system = (
        "You are a music expert. Reply with ONLY valid JSON, no markdown or explanation. "
        "Return a JSON array of exactly 7 objects. Each object must have: "
        '"title" (string), "artist" (string), "why" (one short sentence explaining the similarity). '
        "Choose real, well-known songs that are musically or thematically similar to the reference track "
        "(same genre, era, production style, collaborators, or clear sonic kinship). "
        f'Do not include "{seed_norm["title"]}" by {seed_norm["artist"]} or any obvious duplicate title+artist.'
    )
    user = (
        f'The reference track is "{seed_norm["title"]}" by {seed_norm["artist"]}.\n'
        "Suggest 7 other songs a listener would enjoy if they love that track."
    )
    cp = body.context_prompt.strip()
    if cp:
        user += f'\n\nFor additional context, the user\'s earlier request was: "{cp}"'
    favs = _trim_favorites(body.favorites)
    if favs:
        user += favorites_context_block(favs)

    parse_errors: list[str] = []
    similar_songs: list[dict] | None = None
    duplicate_retries = 0
    max_duplicate_retries = 3

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
                        "Some suggestions duplicated the reference track or each other, "
                        "or you returned the wrong count. Reply again with ONLY a JSON array "
                        f'of exactly 7 objects. None may be "{seed_norm["title"]}" by '
                        f'{seed_norm["artist"]}. All 7 must be distinct real songs.'
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
                            "Reply again with ONLY a valid JSON array of exactly 7 objects."
                        ),
                    }
                )

            content = request_recommendations(client, messages)
            try:
                parsed = parse_song_json(content)
                songs = [normalize_song_item(x) for x in parsed if isinstance(x, dict)]
                if len(songs) < 7:
                    raise ValueError(f"Expected at least 7 songs, got {len(songs)}")
                songs = songs[:7]
                break
            except (json.JSONDecodeError, ValueError) as e:
                parse_errors.append(str(e))

        if songs is None:
            raise HTTPException(
                status_code=502,
                detail="Could not parse model output as JSON after retries: "
                + " | ".join(parse_errors),
            )

        seen: set[tuple[str, str]] = {seed_key}
        filtered: list[dict] = []
        for s in songs:
            k = track_key(s["title"], s["artist"])
            if k == seed_key or k in seen:
                continue
            seen.add(k)
            filtered.append(s)

        if len(filtered) == 7:
            similar_songs = filtered
            break

        duplicate_retries += 1
        parse_errors = []

    if similar_songs is None:
        raise HTTPException(
            status_code=502,
            detail="Could not get 7 distinct similar songs after several tries; try again.",
        )

    out = [seed_norm] + similar_songs
    return {"songs": out}


@app.post("/api/recommend/one")
async def recommend_one(body: ReplaceSongRequest) -> dict:
    client = get_client()
    other_keys: set[tuple[str, str]] = {
        track_key(o.title, o.artist) for o in body.others if o.title or o.artist
    }
    other_keys |= {
        track_key(f.title, f.artist) for f in _trim_favorites(body.favorites)
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
    favs = _trim_favorites(body.favorites)
    if favs:
        user += favorites_context_block(favs)

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
