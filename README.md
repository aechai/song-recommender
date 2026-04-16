# Song Recommender (MP1)

A FastAPI web app that recommends songs using Together AI.

## Features

- FastAPI backend with a recommendation API endpoint
- Together AI integration using `meta-llama/Llama-3-70b-chat-hf`
- Automatic fallback model if the primary model is unavailable
- Dark-mode frontend with a modern card-based layout
- Root route (`/`) serves the `index.html` UI

## Project Structure

- `main.py` - FastAPI app and Together API integration
- `index.html` - Frontend UI
- `requirements.txt` - Python dependencies
- `.env` - Environment variables (you create this locally)

## Requirements

- Python 3.10+ (3.11 recommended)
- A Together API key

## Setup

1. Open a terminal in the project folder:

```powershell
cd "C:\Users\ssadi\OneDrive\Desktop\song-reccomender"
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Create/update `.env` in the project root:

```env
TOGETHER_API_KEY=your_together_api_key_here
```

## Run the App

Use a clean port (recommended: `8010`):

```powershell
uvicorn main:app --reload --port 8010
```

Open in your browser:

- <http://127.0.0.1:8010>

## API

### `POST /api/recommend`

Request body:

```json
{
  "prompt": "upbeat gym songs"
}
```

Response shape:

```json
{
  "songs": [
    {
      "title": "Song Title",
      "artist": "Artist Name",
      "why": "Short reason for recommendation"
    }
  ]
}
```

## Troubleshooting

- `ERR_CONNECTION_REFUSED`
  - Server is not running. Start `uvicorn` again.
- Blank page / wrong output on `8000`
  - Another process may be using that port. Run on `8010` or another free port.
- Recommendations fail with 502
  - Check your API key in `.env`.
  - Confirm internet access.
  - Retry request (model output can occasionally be malformed; app retries automatically).

## Notes

- Do not commit `.env` to source control.
- If port `8010` is busy, use another port such as `8011` and open that URL instead.
