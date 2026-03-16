# Chrome Extension for BGA Innovation Tracker

## Overview

Create a Chrome extension (Manifest V3) that adds a button to Chrome's extension toolbar. Clicking the button extracts Innovation game data from the active BGA tab and sends it to a local FastAPI server that runs the existing processing pipeline. This replaces the Playwright-based fetch step and lays groundwork for future in-browser processing and overlays.

## Context

- Files involved: `src/bga_tracker/innovation/pipeline.py`, `src/bga_tracker/innovation/fetch.py`, `src/bga_tracker/innovation/paths.py`, `scripts/fetch_full_history.js`
- Related patterns: The existing `fetch_full_history.js` script already contains the BGA extraction logic (calls `notificationHistory` API, reads `gameui.gamedatas`). The extension reuses this logic.
- Dependencies: `fastapi`, `uvicorn` (new Python deps); no new JS deps

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Implementation Steps

### Task 1: Create Chrome Extension

**Files:**
- Create: `extension/manifest.json`
- Create: `extension/background.js`
- Create: `extension/extract.js`
- Create: `extension/icons/` (16, 48, 128 px placeholder icons)

- [x] Create `extension/manifest.json` (Manifest V3) with `action` (toolbar button with icon and tooltip "Track Innovation Game"), permissions for `activeTab` and `scripting`, host permission for `localhost`. No `default_popup` — clicking the toolbar icon triggers `chrome.action.onClicked` directly.
- [x] Create placeholder icons in `extension/icons/` (icon-16.png, icon-48.png, icon-128.png).
- [x] Create `extension/extract.js` — the extraction function that runs in the page's MAIN world. Reuses the logic from `scripts/fetch_full_history.js`: reads `gameui.gamedatas`, calls `notificationHistory` API, returns `{players, gamedatas, packets}` object.
- [x] Create `extension/background.js` — service worker that: (1) listens for `chrome.action.onClicked`, (2) checks the active tab URL is a BGA game page, (3) sets badge to "..." (extracting), (4) injects `extract.js` into the active tab using `chrome.scripting.executeScript({world: "MAIN"})`, (5) receives the returned data, (6) POSTs it to `http://localhost:8787/extract` with the table URL, (7) sets badge to a green checkmark on success or red "ERR" on failure, (8) clears badge after a few seconds.
- [x] Manually test: load extension in Chrome via chrome://extensions (developer mode), verify the icon appears in the toolbar, navigate to a BGA Innovation game, click the toolbar icon (server not running yet — expect badge "ERR" after extraction, but extraction itself should succeed).

### Task 2: Create Local HTTP Server

**Files:**
- Create: `src/bga_tracker/innovation/server.py`
- Modify: `pyproject.toml` (add fastapi, uvicorn dependencies)

- [x] Add `fastapi` and `uvicorn` to `pyproject.toml` dependencies.
- [x] Create `src/bga_tracker/innovation/server.py` with a FastAPI app:
  - `POST /extract` endpoint: accepts JSON body `{url: str, raw_data: {players, gamedatas, packets}}`, saves `raw_log.json` to the appropriate data directory, runs processing pipeline (process_log, track_state, format_state), returns `{status, table_dir, summary_path}`.
  - CORS middleware allowing `chrome-extension://` origins and localhost.
  - Reuse existing functions: `parse_bga_url()`, `create_table_dir()`, `_determine_opponent()` from paths/fetch modules.
- [x] Write tests for the `/extract` endpoint using FastAPI's TestClient and fixture data from `tests/innovation/fixtures/`.
- [x] Run project test suite — must pass before task 3.

### Task 3: Add CLI serve Command

**Files:**
- Modify: `src/bga_tracker/innovation/pipeline.py`

- [x] Add a `serve` subcommand (or `--serve` flag) to the CLI that starts the FastAPI server with uvicorn on a configurable port (default 8787).
- [x] Update existing pipeline code so the server's `/extract` endpoint reuses the same `run_pipeline()` flow (with raw data passed in-memory instead of fetched via Playwright).
- [x] Write tests for the serve CLI argument parsing.
- [x] Run project test suite — must pass before task 4.

### Task 4: Verify Acceptance Criteria

- [x] Manual test: start server with `python -m bga_tracker.innovation.pipeline serve`, load extension, navigate to BGA Innovation game, click the toolbar icon, verify summary.html is generated.
- [x] Run full test suite (`pytest`)
- [x] Run linter if configured
- [x] Verify test coverage meets 80%+

### Task 5: Update Documentation

- [x] Update README.md with Chrome extension setup instructions (load unpacked extension, start server, usage)
- [x] Update CLAUDE.md if internal patterns changed
- [x] Move this plan to `docs/plans/completed/`
