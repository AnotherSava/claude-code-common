# End-to-End Pipeline CLI

## Overview

Add `python -m bga_tracker.innovation.pipeline URL` that automates the full workflow: launch browser, navigate to a BGA Innovation game URL, fetch notification history, process log, track card state, generate summary.html, and open it in the default browser. Also change format_state to read game_state.json instead of re-processing game_log.json.

## Context

- Files involved: `src/bga_tracker/innovation/paths.py` (modify), `src/bga_tracker/innovation/game_state.py` (modify), `src/bga_tracker/innovation/format_state.py` (modify), `src/bga_tracker/innovation/fetch.py` (create), `src/bga_tracker/innovation/pipeline.py` (create)
- Related patterns: existing CLIs (`track_state.py`, `format_state.py`, `process_log.py`), `browse.py` (Playwright + persistent Chrome profile)
- Dependencies: playwright (already in pyproject.toml)

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Implementation Steps

### Task 1: Add URL parsing and table directory creation to paths.py

**Files:**
- Modify: `src/bga_tracker/innovation/paths.py`

- [x] Add `parse_bga_url(url: str) -> str` that extracts the table ID from a full BGA URL like `https://boardgamearena.com/10/innovation?table=815951228`. Parse the `table=` query parameter. Raise ValueError if the URL doesn't contain a table= parameter.
- [x] Add `create_table_dir(table_id: str, opponent: str) -> Path` that creates `data/<TABLE_ID> <opponent>/` and returns the Path (mkdir with parents=True, exist_ok=True)
- [x] Write unit tests for both functions (valid URLs, missing table param, directory creation, idempotent calls)
- [x] Run project test suite - must pass before task 2

### Task 2: Add GameState.from_json() and update format_state to use it

**Files:**
- Modify: `src/bga_tracker/innovation/game_state.py`
- Modify: `src/bga_tracker/innovation/format_state.py`

- [x] Add `GameState.from_json(data: dict, card_db: CardDatabase) -> GameState` classmethod that deserializes game_state.json back into a fully functional GameState. Must reconstruct Card objects, `_groups`, `_resolved_indices`, and `_resolved_counts` so that methods like `opponent_has_partial_information()`, `is_resolved()`, and `resolved_count()` work correctly.
- [x] Change `format_state.main()` to read `game_state.json` via `GameState.from_json()` instead of re-processing `game_log.json`. Update usage string accordingly. Remove the GameLogProcessor import and log processing.
- [x] Write test: serialize a GameState via to_json + GameStateEncoder, then deserialize via from_json, verify all zones and query methods return the same results as the original
- [x] Write test: verify format_state.main() reads from game_state.json (use an existing fixture, run track_state to produce game_state.json, then run format_state and verify it produces summary.html)
- [x] Run project test suite - must pass before task 3

### Task 3: Create browser fetch module

**Files:**
- Create: `src/bga_tracker/innovation/fetch.py`

- [x] Create `fetch_game_data(url: str) -> tuple[dict, Path, str]` that:
  - Parses table_id from the URL via `parse_bga_url()`
  - Launches Playwright with persistent Chrome profile (`.chrome_bga_profile`, same path as browse.py)
  - Headed mode (provides visual feedback, consistent with browse.py)
  - Navigates to the provided URL
  - Detects login-required state: after navigation settles, check if the page has a login form or redirected away from the game (e.g. page URL contains `/account` or lacks `table=`). Raise a clear error telling the user to log in first via `python -m browser.browse https://boardgamearena.com` and log in manually through the browser.
  - Waits for `gameui` global via `page.wait_for_function("() => typeof gameui !== 'undefined' && gameui.gamedatas")`
  - Reads and evaluates `scripts/fetch_full_history.js` via `page.evaluate`
  - Parses JSON result, raises on error responses
  - Determines opponent from players dict (the player whose name != player_name from Config)
  - Creates table directory via `create_table_dir()`
  - Saves `raw_log.json` to table directory
  - Returns `(raw_data_dict, table_dir_path, opponent_name)`
  - Closes browser context in a finally block
- [x] Write test with mocked Playwright (verify URL passed through, file saving, error on login redirect, opponent detection)
- [x] Run project test suite - must pass before task 4

### Task 4: Create pipeline CLI

**Files:**
- Create: `src/bga_tracker/innovation/pipeline.py`

- [x] CLI: `python -m bga_tracker.innovation.pipeline URL [--no-open] [--skip-fetch]`
  - URL: full BGA game URL like `https://boardgamearena.com/10/innovation?table=815951228`
  - `--no-open`: skip opening summary.html in default browser
  - `--skip-fetch`: skip browser fetch step, use existing raw_log.json (useful for re-processing without a live BGA session). Requires table directory to already exist — find via `find_table()` using table_id parsed from the URL.
- [x] Implement pipeline steps with console progress messages:
  1. Parse table_id from URL via `parse_bga_url()`
  2. `fetch_game_data(url)` → saves `raw_log.json` (skipped with `--skip-fetch`)
  3. `process_raw_log(raw_data)` → saves `game_log.json`
  4. `GameLogProcessor(card_db, players, player_name).process_log(game_log_path)` → `GameState`
  5. Save `game_state.json` via `GameStateEncoder`
  6. `SummaryFormatter(game_state, ...).render()` → saves `summary.html`
  7. `webbrowser.open()` on summary.html (unless `--no-open`)
- [x] Write test for `--skip-fetch` mode using an existing test fixture (exercises the process_log → track → format chain end-to-end without a browser)
- [x] Run project test suite - must pass before task 5

### Task 5: Verify acceptance criteria

- [x] Manual test: run full pipeline with a real BGA game URL
- [x] Run full test suite: `python -m pytest tests/ -v`
- [x] Verify test coverage meets 80%+

### Task 6: Update documentation

- [x] Update README.md with new pipeline command usage and examples
- [x] Update CLAUDE.md if internal patterns changed
- [x] Move this plan to `docs/plans/completed/`
