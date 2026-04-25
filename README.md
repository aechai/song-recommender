# Song Recommender

A small **FastAPI** app with a static frontend that suggests **20 songs at a time** from a natural-language prompt, using **Together AI** (Llama 3 chat models). It includes **30-second Apple Music previews** (via Apple’s public Search API), **Saved tracks**, **saved playlists**, **“more like this track”** flows, and **optional YouTube export** via Google OAuth. There is **no user database**; Saved tracks and playlists live in the **browser’s `localStorage`**.

---

## Features

| Area | What it does |
|------|----------------|
| **Recommendations** | Enter a vibe, genre, artist, or scenario; the model returns **20** tracks with a short **why** for each. |
| **Music personality quiz** | On **`/personality-quiz`**, answer **5** multiple-choice questions; the model returns a **musical persona** plus **20** song picks with a short **why** each (answers are sent as `Quiz Results: …` to **`POST /api/recommend`**). **Clean Mode** sits beside **Find My Persona**. Same previews, optional Saved-as-context, redo / more-like, hearts, and save-playlist as the main UI. |
| **Clean Mode** | Optional toggle on **`/`** and **`/personality-quiz`**. When on, requests include **`clean_mode: true`**; the backend adds a strict system-prompt rule so the model should suggest only **clean** or **radio-edit** versions (no explicit lyrics / parental-advisory picks). Applies to initial recommendations, **Redo**, and **More like this**. |
| **Saved as context** | Optional checkbox sends up to **40** saved tracks (title + artist) with the prompt so picks align with taste. |
| **Redo one track** | Replace a single card with another song that still fits the same prompt (avoids duplicates with the rest of the list and favorites). |
| **More like this** | Pick one result; the app fetches **19** similar songs and shows **20** tracks total with your pick **first**. |
| **Previews** | Per-track **Play** and a small **playlist preview bar** play **~30s** clips when Apple’s catalog returns a `previewUrl`. |
| **Saved tracks** | Heart tracks on the home page; manage them on **Saved** (`/favorites`) with remove and preview-in-order. |
| **Saved playlists** | **Save playlist** on the home page stores the current playlist; names are auto **`Playlist #1`**, **`Playlist #2`**, … (next number = max existing `Playlist #n` + 1). Up to **40** playlists kept (newest first). |
| **Saved page tabs** | On **`/favorites`**, switch between **Saved** and **Saved playlists** without leaving the page. |
| **YouTube export** | Link a Google account on **`/account`**, then export the current playlist, any saved playlist, or all saved tracks to a YouTube playlist. |
| **EN/ES localization** | All app pages include an **EN/ES** toggle. UI labels, placeholders, quiz question/options, and status copy switch language and persist via `localStorage` (`songRecommenderLanguage`). |
| **In-place description translation** | Switching EN/ES does **not** regenerate recommendations. Existing card **descriptions (`why`)** are translated in place via **`POST /api/translate-descriptions`**, keeping the same songs/order. |


---

## Tech stack

- **Backend:** FastAPI, Pydantic, httpx, python-dotenv, **Together** Python SDK.
- **Models (Together):** Primary `meta-llama/Llama-3-70b-chat-hf`, fallback `meta-llama/Llama-3.3-70B-Instruct-Turbo` if the primary call fails.
- **Previews:** Apple iTunes Search API (`https://itunes.apple.com/search`) — **no API key**.
- **Frontend:** Static `index.html`, `personality-quiz.html`, `favorites.html`, `playlists.html`, `account.html` (vanilla JS, `localStorage`).

---

## Project structure

| Path | Role |
|------|------|
| `main.py` | FastAPI app, Together chat calls, JSON parsing/retries, iTunes preview proxy. |
| `index.html` | Main recommender UI (describe-based flow). |
| `personality-quiz.html` | Musical Personality Quiz UI (separate page). |
| `favorites.html` | Saved tracks + in-page **Saved playlists** tab. |
| `playlists.html` | Standalone saved-playlists view (also shown in the Saved page tab). |
| `account.html` | Link/unlink Google account for YouTube export. |
| `requirements.txt` | Python dependencies. |
| `.env` | Local secrets (Together). **Do not commit.** |

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
| `/personality-quiz` | `personality-quiz.html` |
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
  "favorites": [{ "title": "Optional", "artist": "Taste hints" }],
  "clean_mode": false
}
```

- `favorites` is optional; when present, the backend trims to **40** entries and adds taste context to the model prompt.
- `clean_mode` is optional (default **`false`**). When **`true`**, the system message includes a **CRITICAL** instruction: only suggest **clean** or **radio-edit** tracks; do not suggest songs with explicit lyrics or parental-advisory warnings. The same suffix applies to **quiz** payloads (`Quiz Results: …`).

Response:

```json
{
  "songs": [
    { "title": "…", "artist": "…", "why": "…" }
  ]
}
```

The UI expects **20** songs (default); the client renders whatever list is returned after normalization.

### `POST /api/recommend/one`

Replace one track in a playlist context.

Body (conceptually):

```json
{
  "prompt": "same user request as the list",
  "replace": { "title": "…", "artist": "…" },
  "others": [{ "title": "…", "artist": "…" }],
  "favorites": [],
  "clean_mode": false
}
```

- Optional **`clean_mode`**: same behavior as **`POST /api/recommend`** when set to **`true`**.

Response: `{ "song": { "title", "artist", "why" } }`.

### `POST /api/recommend/similar`

**More like this:** body includes `seed` (title/artist), optional `seed_why`, optional `context_prompt` (original textarea), optional `favorites`, optional **`clean_mode`** (boolean; when **`true`**, the same clean/radio-edit system suffix is applied).

Response: `{ "songs": [ … ] }` — **20** items: the **seed first**, then **19** similar tracks.

### `GET /api/preview`

Query: `title`, `artist` (at least one required).

Response: `{ "preview_url": "<https://…>" }` or **404** if no preview is found.

### `POST /api/translate-descriptions`

Translate existing card description lines without changing song identities/order.

Body:

```json
{
  "descriptions": ["Short why #1", "Short why #2"],
  "target_lang": "es"
}
```

- `target_lang` must be `"en"` or `"es"`.
- The backend returns the same number of strings, same order.

Response:

```json
{
  "descriptions": ["Motivo breve #1", "Motivo breve #2"]
}
```

### YouTube export (Google OAuth)

This app can optionally link a Google account and export playlists to YouTube.

- **Link/unlink UI:** open **`/account`**
- **OAuth env vars:** set these in `.env`, then restart `uvicorn`:
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `GOOGLE_REDIRECT_URI` (example: `http://127.0.0.1:8010/auth/google/callback`)
- **Export endpoint:** `POST /api/youtube/export` with body:

```json
{
  "name": "My playlist name",
  "tracks": [{ "title": "…", "artist": "…" }]
}
```

Notes:
- Tokens are stored **in memory** only; restarting the server requires re-linking.
- Export uses YouTube search for each `title + artist` and skips tracks with no match.

---

## Browser storage (`localStorage`)

| Key | Contents |
|-----|----------|
| `songRecommenderFavorites` | Array of `{ title, artist, why? }` for hearted tracks. |
| `songRecommenderSavedPlaylists` | Array of `{ id, name, savedAt, prompt?, tracks: [{ title, artist }] }`. |
| `songRecommenderLanguage` | Current UI language (`"en"` or `"es"`). |

**Clearing site data** removes Saved tracks and playlists.

---

## Current limitations

- **LLM output:** Titles/artists are model-generated; mistakes or obscure picks can occur. The app **retries** on bad JSON and on some duplicate cases for replace/similar flows, but cannot guarantee correctness.
- **Clean Mode:** Steering is **prompt-only** (no store/catalog explicit flags). The model may still name a track whose album has an explicit version elsewhere; users should treat it as a best-effort filter.
- **No user database:** Saved tracks/playlists are **only in that browser**. YouTube linking is **session-only** (in-memory) and requires re-linking after a server restart.
- **Previews only:** Audio is **~30 seconds** from Apple’s catalog when a preview exists; **full streaming** would need Spotify/Apple Music APIs and user login (out of scope here).
- **Preview gaps:** Some regions or tracks may have **no** `previewUrl`; the UI skips or shows an error for that clip.
- **Together usage:** Every recommendation, redo, and similar-songs call uses the **Together API** (cost/latency/rate limits apply).
- **Saved in prompts:** When “use saved” is checked, **titles and artists** are sent to Together to steer taste — do not enable if that is a concern.
- **Playlist naming:** Saved playlists are named **`Playlist #n`** automatically; the original request text is stored separately when present.

---

## Troubleshooting

| Symptom | What to try |
|---------|-------------|
| `ERR_CONNECTION_REFUSED` | Start `uvicorn` again; confirm host/port. |
| Blank or wrong page on a port | Another app may be using that port — try **`8010`**, **`8011`**, etc. |
| `500` / “TOGETHER_API_KEY is not set” | Add the key to **`.env`** in the project root and restart the server. |
| Clicking Link shows an error page | Make sure you set the OAuth variables in `.env` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`) and restart `uvicorn`. Also ensure the redirect URI matches your port. |
| `502` on recommend / similar / redo | Check API key, network, and Together status; retry (models occasionally return non-JSON). |
| Preview always fails | Try a different spelling; not all songs have previews in Apple’s results. |
| Dependencies error on `together` | Run `pip install -r requirements.txt` again from the activated venv. |

---

## Development notes

- **`pytest`** is listed in `requirements.txt` for testing; there may be no tests in-repo yet — safe to ignore for a quick run.
- Do **not** commit `.env`; it should stay in `.gitignore`.

---

## Add-on updates (latest)

- **Stable song identity on language toggle:** Switching EN/ES no longer re-runs recommendation generation for existing cards. The app keeps the same track titles/artists/order and updates only translatable UI + description text.
- **Description translation endpoint:** The backend now includes **`POST /api/translate-descriptions`** for translating existing `why` lines in place while preserving list length/order.
- **Saved page parity:** The Saved tab (`/favorites`) now uses the same in-place description translation behavior as the main and quiz pages.
- **Quiz payload localization:** Quiz option labels are localized, and quiz answer payload text can be language-aware when building the `Quiz Results:` prompt.

---

## Add-on updates (latest + theme pass)

- **Clean Mode:** **Explicit content filter** via a sage/rose-gold **Clean Mode** toggle on **`index.html`** (near the describe form actions) and **`personality-quiz.html`** (beside **Find My Persona**). Sends **`clean_mode: true`** on **`POST /api/recommend`**, **`POST /api/recommend/similar`**, and **`POST /api/recommend/one`** when enabled; `main.py` appends the strict clean/radio-edit instruction to the system prompt for those calls (including quiz `Quiz Results:` flows).
- **Aesthetic UI overhaul:** `index.html`, `personality-quiz.html`, `favorites.html`, `playlists.html`, and `account.html` were updated to a soft Pinterest/aura visual style (dreamy gradients, glassmorphism panels/cards, rounded corners, and lifted gradient buttons) while preserving existing functionality.
- **Typography refresh:** UI now uses a serif-forward headline style (`Playfair Display`) with clean sans-serif body copy (`Montserrat`) for a more editorial/pinterest feel.
- **Persona visual polish:** The quiz persona area includes subtle glow/sparkle treatment for stronger emphasis.
- **Persona name translation on toggle:** On the quiz page, switching EN/ES now translates the **persona name text itself** (not only the “Your musical persona” label), using the same in-place translation approach.

---
