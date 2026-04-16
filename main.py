import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from together import Together

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
MODEL_ID = "meta-llama/Llama-3-70b-chat-hf"
FALLBACK_MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct-Turbo"

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


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html")


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
        normalized.append(
            {
                "title": str(item.get("title", "Unknown")),
                "artist": str(item.get("artist", "Unknown")),
                "why": str(item.get("why", "")),
            }
        )

    return {"songs": normalized}
