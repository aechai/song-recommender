# Song Recommender

A small **FastAPI** app with a static frontend that suggests **8 songs at a time** from a natural-language prompt, using **Together AI** (Llama 3 chat models). It includes **30-second Apple Music previews** (via Apple’s public Search API), **favorites**, **saved playlists**, and **“more like this track”** flows. There is **no user database**; favorites and playlists live in the **browser’s `localStorage`**.

---

## Features

| Area | What it does |
|------|----------------|
| **Recommendations** | Enter a vibe, genre, artist, or scenario; the model returns **8** tracks with a short **why** for each. |
| **Favorites as context** | Optional checkbox sends up to **40** saved favorites (title + artist) with the prompt so picks align with taste. |
| **Redo one track** | Replace a single card with another song that still fits the same prompt (avoids duplicates with the rest of the list and favorites). |
| **More like this** | Pick one result; the app fetches **7** similar songs and shows **8** tracks total with your pick **first**. |
| **Previews** | Per-track **Play** and a small **playlist preview bar** play **~30s** clips when Apple’s catalog returns a `previewUrl`. |
| **Favorites** | Heart tracks on the home page; manage them on **Favorite tracks** (`/favorites`) with remove and preview-in-order. |
| **Saved playlists** | **Save playlist** on the home page stores the current 8 tracks; names are auto **`Playlist #1`**, **`Playlist #2`**, … (next number = max existing `Playlist #n` + 1). Up to **40** playlists kept (newest first). |
| **Playlists page** | **`/playlists`** lists saved playlists, optional saved **request** text, ordered tracks (title — artist), and delete. |
| **Favorites page tabs** | On **`/favorites`**, switch between **Favorite tracks** and **Saved playlists** without leaving the page. |

---

## Tech stack

- **Backend:** FastAPI, Pydantic, httpx, python-dotenv, **Together** Python SDK.
- **Models (Together):** Primary `meta-llama/Llama-3-70b-chat-hf`, fallback `meta-llama/Llama-3.3-70B-Instruct-Turbo` if the primary call fails.
- **Previews:** Apple iTunes Search API (`https://itunes.apple.com/search`) — **no API key**.
- **Frontend:** Static `index.html`, `favorites.html`, `playlists.html` (vanilla JS, `localStorage`).

---

## Project structure

| Path | Role |
|------|------|
| `main.py` | FastAPI app, Together chat calls, JSON parsing/retries, iTunes preview proxy. |
| `index.html` | Main recommender UI. |
| `favorites.html` | Favorites + in-page **Saved playlists** tab. |
| `playlists.html` | Standalone saved-playlists view. |
| `account.html` | Account page for linking streaming services (OAuth). |
| `requirements.txt` | Python dependencies. |
| `.env` | Local secrets (Together + OAuth). **Do not commit.** |

---

## Prerequisites

- **Python 3.10+** (3.11+ recommended).
- A **[Together AI](https://www.together.ai/)** API key.
- Network access for Together and Apple’s search endpoint.

---

## Setup

1. Open a terminal in the project folder (note the folder name may be `song-recommender`):

```powershell
cd "path\to\song-recommender"
```

2. Create a virtual environment (recommended), then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

3. Create **`.env`** in the project root:

```env
TOGETHER_API_KEY=your_together_api_key_here
```

---

## Run the app

Use a free port (example **8010**):

```powershell
uvicorn main:app --reload --port 8010
```

Then open **http://127.0.0.1:8010** in your browser.

---

## Served pages (GET)

| Route | File |
|------|------|
| `/` | `index.html` |
| `/favorites` | `favorites.html` |
| `/playlists` | `playlists.html` |
| `/account` | `account.html` |

---

## HTTP API

All recommendation endpoints expect **JSON** bodies and return JSON. Errors use FastAPI’s default shapes (`detail` string or validation errors).

### `POST /api/recommend`

Body:

```json
{
  "prompt": "Late-night synth-pop, dreamy vocals",
  "favorites": [{ "title": "Optional", "artist": "Taste hints" }]
}
```

- `favorites` is optional; when present, the backend trims to **40** entries and adds taste context to the model prompt.

Response:

```json
{
  "songs": [
    { "title": "…", "artist": "…", "why": "…" }
  ]
}
```

The UI expects **8** songs; the model is instructed accordingly, but the client renders whatever list is returned after normalization.

### `POST /api/recommend/one`

Replace one track in a playlist context.

Body (conceptually):

```json
{
  "prompt": "same user request as the list",
  "replace": { "title": "…", "artist": "…" },
  "others": [{ "title": "…", "artist": "…" }],
  "favorites": []
}
```

Response: `{ "song": { "title", "artist", "why" } }`.

### `POST /api/recommend/similar`

**More like this:** body includes `seed` (title/artist), optional `seed_why`, optional `context_prompt` (original textarea), optional `favorites`.

Response: `{ "songs": [ … ] }` — **8** items: the **seed first**, then **7** similar tracks.

### `GET /api/preview`

Query: `title`, `artist` (at least one required).

Response: `{ "preview_url": "<https://…>" }` or **404** if no preview is found.

---

## Browser storage (`localStorage`)

| Key | Contents |
|-----|----------|
| `songRecommenderFavorites` | Array of `{ title, artist, why? }` for hearted tracks. |
| `songRecommenderSavedPlaylists` | Array of `{ id, name, savedAt, prompt?, tracks: [{ title, artist }] }`. |

Counts in the nav update when storage changes (e.g. another tab). **Clearing site data** removes favorites and playlists.

---

## Linking streaming accounts (OAuth)

This project now supports real OAuth “linking” for:

- **Spotify** (OAuth + PKCE)
- **Google** (OAuth; used for YouTube/YouTube Music access)

To enable the **Link** buttons on `/account`, add these to your `.env` (see `.env.example`):

- `SESSION_SECRET`
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_REDIRECT_URI`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`

For local dev, your redirect URIs should match your `uvicorn` port, e.g.:

- Spotify: `http://127.0.0.1:8010/auth/spotify/callback`
- Google: `http://127.0.0.1:8010/auth/google/callback`

### OAuth endpoints

- **Spotify**
  - `GET /auth/spotify/login`
  - `GET /auth/spotify/callback`
  - `POST /auth/spotify/logout`
- **Google**
  - `GET /auth/google/login`
  - `GET /auth/google/callback`
  - `POST /auth/google/logout`
- **Status used by the Account page**
  - `GET /api/auth/status`

### Notes

- OAuth tokens are stored in a **server-side session cookie** (no database).
- Apple Music linking is **not implemented** (requires MusicKit + developer token).


## Current limitations

- **LLM output:** Titles/artists are model-generated; mistakes or obscure picks can occur. The app **retries** on bad JSON and on some duplicate cases for replace/similar flows, but cannot guarantee correctness.
- **No accounts / no server-side library:** Favorites and playlists are **only on that browser** unless you export them yourself (not built in).
- **Previews only:** Audio is **~30 seconds** from Apple’s catalog when a preview exists; **full streaming** would need Spotify/Apple Music APIs and user login (out of scope here).
- **Preview gaps:** Some regions or tracks may have **no** `previewUrl`; the UI skips or shows an error for that clip.
- **Together usage:** Every recommendation, redo, and similar-songs call uses the **Together API** (cost/latency/rate limits apply).
- **Favorites in prompts:** When “use favorites” is checked, **titles and artists** are sent to Together to steer taste — do not enable if that is a concern.
- **Playlist naming:** Saved playlists are named **`Playlist #n`** automatically; the original request text is stored separately when present.

---

## Troubleshooting

| Symptom | What to try |
|---------|-------------|
| `ERR_CONNECTION_REFUSED` | Start `uvicorn` again; confirm host/port. |
| Blank or wrong page on a port | Another app may be using that port — try **`8010`**, **`8011`**, etc. |
| `500` / “TOGETHER_API_KEY is not set” | Add the key to **`.env`** in the project root and restart the server. |
| Clicking Link shows an error page | Make sure you set the OAuth variables in `.env` (`SPOTIFY_CLIENT_ID`, `SPOTIFY_REDIRECT_URI`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`) and restart `uvicorn`. Also ensure the redirect URIs match your port. |
| `502` on recommend / similar / redo | Check API key, network, and Together status; retry (models occasionally return non-JSON). |
| Preview always fails | Try a different spelling; not all songs have previews in Apple’s results. |
| Dependencies error on `together` | Run `pip install -r requirements.txt` again from the activated venv. |

---

## Development notes

- **`pytest`** is listed in `requirements.txt` for testing; there may be no tests in-repo yet — safe to ignore for a quick run.
- Do **not** commit `.env`; it should stay in `.gitignore`.

---
