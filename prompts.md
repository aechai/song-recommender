# Prompts — Song Recommender (MP1+)

This file captures the **canonical prompts** used to iteratively build and extend the Song Recommender project. Each prompt includes:

- **Prompt **: The exact request to provide to an LLM/agent.
- **Effects**: What the prompt should create, update, or investigate (files, endpoints, UI behavior, documentation).

---

## Prompt 1 — Initial MVP build (FastAPI + Together + UI)

### Prompt 
Build a FastAPI application for a Song Recommender (MP1) with a static frontend.

Requirements:

- Create `main.py` that uses the `together` Python library to request recommendations from the model `meta-llama/Llama-3-70b-chat-hf`.
- Create `requirements.txt` including: `fastapi`, `uvicorn`, `together`, and `python-dotenv`.
- Create `index.html` implementing a modern, dark-mode UI.
  - The UI must call the backend using `fetch` and render returned songs as **card** components.
- Ensure the backend serves `index.html` at the root route `/`.

### Effects
- **Backend**: A FastAPI app exists in `main.py`, loads environment variables via `python-dotenv`, and uses Together for chat completions to generate song recommendations.
- **Dependencies**: `requirements.txt` exists with the specified packages.
- **Frontend**: `index.html` exists with a dark-themed, modern UI that requests recommendations and displays results as cards.
- **Routing**: `GET /` serves `index.html` (not JSON).

---

## Prompt 2 — Frontend UI refinement (dark-mode, “Why this?”)

### Prompt 
Create an `index.html` file that serves as the frontend for the recommender.

UI/UX requirements:

- Use a modern **dark-mode** aesthetic with a **card-based** layout.
- Provide an input box for the user’s **mood** and a button to request recommendations.
- When results return, render them as cards and include a **“Why this?”** badge/label on each song card to show the rationale.

### Effects
- **Frontend**: `index.html` contains a mood input, a submit button, and a results area.
- **Rendering**: Recommendations are presented as cards; each card visibly includes a “Why this?” element tied to that song’s explanation.
- **Integration**: The UI uses `fetch` to call the backend and updates the page without reloads.

---

## Prompt 3 — Fix blank page + strengthen “Why” generation

### Prompt 
The app is showing a blank page. Update the `serve_index` function in `main.py` to serve the frontend using a relative path.

Implementation requirements:

- Change the root route handler to return `FileResponse("index.html")` (relative path), rather than using an absolute/fragile path.
- Update the system prompt used for recommendations so the model **explicitly explains** why each song was chosen, using the user’s specific input.

### Effects
- **Bug fix**: `GET /` reliably returns the `index.html` file so the UI is visible when run from the project root.
- **Model output quality**: Each returned song includes a concrete, input-specific “why” explanation (not generic).
- **Contract consistency**: Backend response still matches what the UI expects (songs with title/artist/why or equivalent fields).

---

## Prompt 4 — Project documentation

### Prompt 
Create a `README.md` that describes the Song Recommender project and its features.

Minimum requirements:

- Explain what the project is and what it does.
- Include setup instructions, required environment variables, and how to run the app.
- Describe key user workflows (request recommendations, view results, etc.).

### Effects
- **Documentation**: `README.md` exists and provides an onboarding path (install → configure → run → use).
- **Clarity**: Features and usage are understandable without reading the source code.

---

## Prompt 4b — Git hygiene and secrets protection

### Prompt 
Create a `.gitignore` file (or update the existing one) to prevent secrets from being committed.

Minimum requirements:

- Ensure `.env` is ignored so API keys are never uploaded to GitHub.

### Effects
- **Security**: `.env` is excluded from version control.
- **Developer experience**: Common Python/venv and OS artifacts are also ignored (as appropriate).

---

## Prompt 5 — Increase recommendation count (8 → 20)

### Prompt 
Update the recommender so it generates **20** song recommendations per request instead of **8**.

Constraints:

- Ensure both the backend prompt/instructions and the frontend rendering logic support 20 results.

### Effects
- **Backend**: The LLM is instructed to return 20 songs; server-side parsing/validation supports 20.
- **Frontend**: UI layout accommodates 20 cards without breaking usability (scrolling/grid responsiveness).

---

## Prompt 6 — Musical Personality Quiz feature (persona + songs)

### Prompt 
Add a **Musical Personality Quiz** feature to the Song Recommender.

Frontend requirements:

- Add a new section for a “Musical Personality Quiz” with **5** multiple-choice questions:
  - Energy
  - Environment
  - Social Style
  - Lyrics
  - Novelty
- Add a **“Find My Persona”** button.

Logic requirements:

- Write JavaScript that combines the 5 answers into a single string starting with `Quiz Results:` and send it to the recommendation endpoint (`/recommend` as specified).

Backend requirements:

- Update the system prompt so that if the input starts with `Quiz Results:`, the AI:
  - Identifies a **Musical Persona** name (example: “The Melancholic Explorer”)
  - Returns **5** matching songs

Styling requirements:

- Keep styling consistent with the dark-mode theme.
- Display the **Musical Persona** prominently at the top of results.

### Effects
- **Frontend**: Quiz UI exists with 5 multiple-choice questions and a CTA button.
- **Payload shaping**: Client sends a single `Quiz Results: ...` string constructed from answers.
- **Backend behavior switch**: Inputs prefixed with `Quiz Results:` trigger persona naming + a smaller recommendations list (5 songs).
- **UI output**: Persona is displayed clearly; results render similarly to normal recommendations.

---

## Prompt 7 — README update only (no rewrite)

### Prompt 
Update `README.md` to reflect the new updates to the app. Do not rewrite the README from scratch; only update it to include new features and usage details.

Constraints:

- Preserve existing sections and tone.
- Add/modify content only where necessary for accuracy.

### Effects
- **Documentation accuracy**: README matches the current implementation (routes, features, env vars, workflows).
- **Minimal diffs**: Changes are incremental updates rather than a full restructure.

---

## Prompt 8 — Advanced feature set (implementation + feasibility + ideation)

### Prompt 
Implement and/or investigate the following enhancements for the Song Recommender. Follow each item’s constraints carefully (some require implementation; others require feasibility analysis only; some require no code changes).

### Effects (expected by sub-feature)

#### Random playlist description button (implement)
- **UI**: Add a button that generates a completely random playlist description (independent of user input).
- **Behavior**: The generated description populates the playlist-description input/output so users can discover recommendations without knowing what they want.

#### Redo per song suggestion (implement)
- **Per-card control**: Add a “Redo” control per recommended song.
- **Behavior**: Re-generate only that song using the original prompt/context, replacing just that one track while leaving the rest unchanged.

#### Preview/play snippet per track (implement)
- **Per-card control**: Add a “Play preview” control to each track.
- **Behavior**: Plays a short audio snippet (preview).
- **States**: Include loading/error states when a preview is unavailable.

#### In-app playable playlist (feasibility only)
- **Deliverable**: Document whether an in-app playlist of “actual” recommended songs is possible.
- **Include**: Technical requirements, constraints (APIs/DRM), and a recommended approach.
- **Constraint**: Do not implement unless explicitly requested later.

#### YouTube playlist creation (feasibility only; do not implement yet)
- **Deliverable**: Outline whether the app can create a YouTube playlist containing recommended songs.
- **Include**: Required APIs, authentication flow, and implementation steps.
- **Constraint**: Do not make code changes for this item.

#### Favorite/heart button (implement)
- **Per-card control**: Add a Heart (favorite) button.
- **Behavior**: Persist favorites to a durable list (e.g., browser storage) so they remain across reloads.

#### Favorites page (implement)
- **Page/view**: Add a dedicated favorites page that lists favorited songs.
- **Behavior**: Support removing/unfavoriting items.

#### Playback control icons (implement)
- **Icons**: Use standard media icons for playback controls:
  - Play
  - Skip ahead
  - Skip back
  - Stop
- **Mapping**: Ensure each icon maps to its corresponding action for previews.

#### Preview controls on Favorites page (implement)
- **Reuse**: The Favorites page should reuse the same preview playback UI (including any mini “preview playlist” behavior and per-track controls) as the recommendations page.

#### Recommend using favorites (implement)
- **Feature**: Allow recommendations to be generated using favorited tracks as input signals (seed tracks/artist/genre inference).
- **Constraint**: Still support the original prompt-based workflow.

#### Feature ideation only (do not implement yet)
- **Deliverable**: Propose additional high-value feature ideas, prioritized with brief justification.
- **Constraint**: Do not change the codebase for this item.

#### “More like this track” (implement)
- **Per-card action**: Add “More like this track”.
- **Behavior**: When selected, re-query to fetch **8** similar songs including the selected track.
- **UI update**: Replace the results list with the new set.

#### Save playlist button (implement)
- **UI**: Add a “Save playlist” button.
- **Behavior**: Persist the current generated playlist (tracks + metadata) for later viewing.

#### Saved playlists tab on Favorites page (implement)
- **Favorites page**: Add a “Saved playlists” tab/section listing all saved playlists and allowing open/view.

#### Shorter playlist naming; no per-song descriptions (implement)
- **Saved playlists UI**: Remove individual song descriptions (if present) for saved playlists.
- **Display**: Use a shorter playlist label/title.

#### Auto-generate playlist title (implement)
- **Constraint**: Do not ask the user for a playlist title.
- **Behavior**: Auto-generate a short title derived from the user’s request/prompt.

#### Sequential playlist naming (alternative implementable option)
- **Behavior**: Name playlists `Playlist #<number>` with stable, consistent numbering.

#### README update (implement docs)
- **Docs**: Update README with setup/run instructions, env vars, feature list, usage guide, known limitations, and relevant API/auth constraints.

#### Account linking page (multi-service) (implement)
- **UI + data model**: Add an account page allowing linking external music services (Spotify, YouTube Music, and one additional popular service).
- **State**: Define linked/unlinked state and persistence.

#### Implement streaming account linking (implement)
- **OAuth**: Implement actual OAuth for selected services.
- **Security**: Secure token handling (storage, refresh, unlink/revoke behavior).

#### Selectable recommendation count (implement)
- **UI**: Allow user to choose how many songs to generate (reasonable min/max).
- **Backend**: Respect the chosen count.

#### Remove account page (implement removal)
- **Cleanup**: Remove all account-page UI, code paths, data models, and documentation references.

#### UI sizing consistency (implement)
- **Consistency**: Ensure consistent sizing/layout across all pages.
- **Constraint**: The playlists page should be visually smaller (narrower container or reduced density) than other pages while remaining usable/responsive.

#### Google account link + YouTube export (implement)
- **Account page**: Support linking/unlinking a Google account.
- **Export**: After linking, export generated or saved playlists to YouTube.
- **Requirements**: Auth, error handling, success confirmation.

#### Update Navigation Bar (implement)
- **Nav changes (all HTML pages)**:
  - Remove the “Save Playlists” tab entirely.
  - Rename “Favorite Tracks” tab to “Saved”.
  - Apply changes consistently across nav bars, links/buttons, and headings.
  - Remove the dropdown for selecting number of songs to generate and remove the number tracking saved favorites.

#### Export to YouTube fixes + expand placement (implement)
- **Bug fix**: Export to YouTube must create a playlist on the user’s connected Google account.
- **UI**: Add Export to YouTube to:
  - Each saved playlist
  - All of the user’s favorite tracks
- **Concurrency constraint**: User cannot press Save Playlist while exporting to YouTube.

#### Status toast (implement)
- **UI**: Convert status text into a floating toast near the bottom-middle of the screen.
- **Behavior**: Toast remains visible during changes; include an “x” button to dismiss it.

#### Update README (implement docs)
- **Docs**: Update README with all existing features; ensure consistency and accuracy across the entire file.

---

## Prompt 9 — EN/ES localization + stable song identity on toggle

### Prompt
Add full English/Spanish localization across the frontend while preserving recommendation identity during language switches.

Requirements:

- Add an **EN/ES** language toggle on all app pages (`index.html`, `personality-quiz.html`, `favorites.html`, `playlists.html`, `account.html`).
- Add `data-i18n`-style translation keys for titles, labels, button text, placeholders, tooltips/ARIA labels, quiz text, and status copy.
- Persist language preference in `localStorage` and restore it on page load.
- For quiz pages, localize the quiz option labels and ensure the quiz payload can be built from language-appropriate answer text.
- Crucial behavior: switching language must **not** regenerate a different recommendation set.
  - Keep existing song cards (title/artist/order) stable.
  - Translate only the existing `why` description text in place.
- Implement a backend endpoint to translate an array of existing descriptions:
  - `POST /api/translate-descriptions`
  - Input: `{ descriptions: string[], target_lang: "en" | "es" }`
  - Output: `{ descriptions: string[] }` with same length/order.
- Update docs to include the localization behavior and translation endpoint.

### Effects
- **Frontend i18n coverage**: Core UI copy and quiz text/options are language-switchable and persistent.
- **Stable recommendations**: EN/ES toggle no longer changes which songs are shown.
- **Description-only translation**: Existing card `why` lines are translated in place through a dedicated API.
- **Backend extension**: `main.py` includes a translation endpoint with JSON-only response constraints and length/order validation.
- **Documentation**: README and prompts history reflect the multilingual feature and the new API contract.

---

## Prompt 10 — Pinterest/aura visual theme pass + persona-name translation

### Prompt
Apply a style-only overhaul across the frontend to match a Pinterest party-girl / dreamy aura aesthetic, while keeping existing logic unchanged.

Requirements:

- Keep all core functionality exactly the same (recommendation flows, quiz behavior, language toggle behavior, YouTube export/search, favorites/playlists interactions).
- Update CSS across main pages to a soft aura palette:
  - Background tones around `#FFF5F7`, `#FCE4EC`, `#F3E5F5`
  - Rose-gold/champagne accent gradients, plus soft muted supporting accents.
- Update typography:
  - Serif-style headers (e.g., `Playfair Display`)
  - Clean sans-serif body text (e.g., `Montserrat`)
- Apply glassmorphism styling to key containers (cards/panels/toasts/nav toggle):
  - Semi-transparent white backgrounds
  - Thin light borders
  - `backdrop-filter: blur(...)`
- Increase corner softness and hover polish:
  - Rounded corners (about `20px+`)
  - Lifted hover shadows on interactive controls.
- Add subtle sparkle/glow emphasis in persona-related UI.
- Ensure persona text localization parity:
  - On quiz language toggle, translate the **persona name value** itself in place.

### Effects
- **Visual cohesion**: All major pages share a unified aura/glassmorphism aesthetic.
- **No behavior regressions**: JavaScript logic and API contracts remain intact.
- **Persona polish + localization**: Persona presentation is visually emphasized and fully translated on EN/ES switches (label + persona name).

---

## Prompt 11 — Explicit content filter (“Clean Mode”)

### Prompt
Add an **Explicit Content Filter** / **Clean Mode** toggle.

**Frontend (`index.html`):**
- Add a stylish toggle (Aura aesthetic: soft rose-gold / sage) labeled **Clean Mode** near the search / describe actions.
- Capture toggle state and send it to the **`/api/recommend`** call (as a JSON field).

**Backend (`main.py`):**
- Accept the flag on recommendation requests.
- When the filter is active, extend the **system** prompt with a strict instruction, for example:
  - **CRITICAL:** Only suggest **“Clean”** or **“Radio Edit”** versions of tracks; do not recommend songs with explicit lyrics or parental-advisory warnings.

Also wire the same flag for **redo** and **more-like-this** flows where applicable, and mirror the UI on **`/personality-quiz`** (e.g. beside **Find My Persona**) with EN/ES copy.

### Effects
- **UI**: `index.html` includes a **Clean Mode** row/toggle (Aura styling) and short hint; toggle is disabled while requests are in flight.
- **UI (quiz)**: `personality-quiz.html` includes the same control (placed with the primary quiz CTA) and localized strings (`q.cleanMode`, `q.cleanModeHint`).
- **Client payload**: When enabled, the client sends **`clean_mode: true`** on **`POST /api/recommend`**, **`POST /api/recommend/similar`**, and **`POST /api/recommend/one`**.
- **Backend**: Pydantic models include optional **`clean_mode`** (default `false`); when `true`, the system message is suffixed with the clean/radio-edit **CRITICAL** rule for main recommend (including `Quiz Results:` quiz path), similar-songs, and single-track replace.
- **Docs**: `README.md` and this file describe the feature, API field, and limitation (prompt-only steering, not catalog-verified).

