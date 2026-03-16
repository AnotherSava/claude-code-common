# TypeScript Migration: Full Chrome Extension Rewrite

## Overview

Rewrite the entire BGA Innovation Tracker as a self-contained Chrome extension in TypeScript. All Python logic moves into the extension. The summary displays in a Chrome side panel with download buttons for game_log.json, game_state.json, and summary.html. The Python server, Playwright fetcher, and Jinja2 templates are eliminated.

This rewrite takes the opportunity to simplify several over-engineered patterns from the original piecemeal Python design.

## Context

- Files involved: All Python source in src/bga_tracker/innovation/, extension/*, templates/innovation/*, assets/card_info.json
- Related patterns: Chrome Manifest V3, side panel API, MAIN world content script injection
- Dependencies: TypeScript, Vite (build), vitest (testing)

## Key Design Simplifications

1. Merge GameState + GameStateTracker into a single GameState class (the original split leaks private fields across the boundary anyway)
2. Use discriminated unions for Card opponent knowledge (`none | partial | exact`) instead of 3 correlated boolean/set fields
3. Use discriminated unions for Action (`named` vs `grouped`) and TemplateCard (`known` vs `unknown`) instead of mutually exclusive nullable fields
4. Drop resolved indices/counts caches - compute on demand (groups have at most 10-15 cards)
5. Drop `bottom_to` from processed log entries (tracked but never used)
6. Simplify game_state.json: store only resolved card name or candidate exclusions, not full candidate lists on every card
7. Replace float-encoded section positions (`1.2` = column 1, order 2) with `{ column: number, order: number }`
8. Replace getattr config lookups with typed `Record<string, SectionConfig>`
9. Inline rendering logic via template literals instead of Jinja2 + DTO layer (TemplateCard/Row/Section become unnecessary)

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Architecture

```
manifest.json          (v3, side_panel, MAIN world content script)
src/
  background.ts        (service worker: orchestrates pipeline, opens side panel)
  extract.ts           (content script: BGA data extraction, MAIN world)
  sidepanel/
    sidepanel.html     (side panel page shell)
    sidepanel.ts       (receives data, triggers render, handles downloads)
    sidepanel.css      (dark theme, card grids, tooltips)
  models/
    types.ts           (all type definitions: Card, CardInfo, GameState, Action, enums)
  engine/
    process_log.ts     (raw BGA packets -> structured game log)
    game_state.ts      (state tracking + constraint propagation, unified class)
  render/
    summary.ts         (GameState -> HTML string via template literals)
    config.ts          (section layout config, visibility/layout defaults)
assets/
  card_info.json
  sprites/             (card sprite sheets)
  icons/               (resource + hex icons)
package.json
tsconfig.json
vite.config.ts
```

Data flow:

1. User clicks extension icon on BGA game page
2. extract.ts (MAIN world) fetches game data from BGA internals
3. background.ts receives data, runs pipeline (processRawLog -> GameState)
4. background.ts opens side panel, sends GameState + game log via chrome.runtime messaging
5. sidepanel.ts renders summary, provides download buttons

## Implementation Steps

### Task 1: Project Setup and Build System

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `vite.config.ts`
- Modify: `manifest.json` (add side_panel permission, update paths for dist/ outputs)
- Create: `src/` directory structure

- [x] Initialize npm project with typescript, vite, vitest, chrome-types
- [x] Configure tsconfig targeting ES2022 with DOM and chrome extension types
- [x] Configure Vite with multiple entry points: background.ts, extract.ts, sidepanel.html
- [x] Update manifest.json: add side_panel permission, point scripts to dist/, add web_accessible_resources for assets
- [x] Copy card_info.json and image assets into assets/
- [x] Verify empty extension builds and loads in Chrome
- [x] Write a smoke test that imports from each entry point without errors

### Task 2: Core Types and Models

**Files:**
- Create: `src/models/types.ts`

- [x] Define CardSet enum (BASE=0, CITIES=3) and Color enum (BLUE through PURPLE)
- [x] Define CardInfo interface (static DB entry: name, age, cardSet, color, spriteIndex, icons)
- [x] Define Card with discriminated union for opponent knowledge:
    type OpponentKnowledge = { kind: "none" } | { kind: "partial"; suspects: Set<string>; closed: boolean } | { kind: "exact"; name: string }
- [x] Define Action as discriminated union: { type: "named"; cardName: string; ... } | { type: "grouped"; age: number; cardSet: CardSet; ... }
- [x] Define GameLog entry types: TransferEntry | MessageEntry (drop bottom_to)
- [x] Build CardDatabase: load card_info.json, group by age+cardSet, provide lookups
- [x] Write unit tests for CardDatabase lookups and Card candidate operations

### Task 3: Log Processing Pipeline

**Files:**
- Create: `src/engine/process_log.ts`

- [x] Port ICON_MAP and SET_MAP constants
- [x] Port expandTemplate (resolve ${key} placeholders with recursive sub-templates)
- [x] Port cleanHtml (BGA HTML markup -> plain text with [icon] and [age] notation)
- [x] Port normalizeName (non-breaking hyphens, combining diacritics)
- [x] Port processRawLog: two-pass BGA packet processing (player-view collection then spectator iteration)
- [x] Write tests using sample BGA packet data: template expansion, HTML cleaning, name normalization, two-pass processing

### Task 4: Game State Engine (unified tracker + state)

**Files:**
- Create: `src/engine/game_state.ts`

- [x] Build unified GameState class holding: decks, hands, boards, scores, revealed, achievements, card groups
- [x] Implement zone accessors returning card arrays by location string
- [x] Implement initGame: deck setup, achievement seeding, initial deal
- [x] Implement processLog: iterate log entries, dispatch to move/revealHand
- [x] Implement deduceInitialHand (pre-log card identification)
- [x] Implement move: source/dest handling, city meld detection, opponent knowledge updates
- [x] Implement constraint propagation (_propagate) with: singleton propagation, hidden singles, naked subsets, suspect propagation
- [x] Implement serialization (toJSON/fromJSON) with simplified format: store resolved name or exclusion set per card instead of full candidate lists
- [x] Write thorough tests: basic moves, singleton propagation, hidden singles, naked subsets, suspect management, meld filtering, serialization round-trip, full game sequence

### Task 5: Extension Entry Points

**Files:**
- Create: `src/extract.ts` (replaces extension/extract.js)
- Create: `src/background.ts` (replaces extension/background.js)

- [x] Port extract.js to TypeScript: BGA data extraction from gameui.gamedatas, ajaxcall for notificationHistory
- [x] Type the raw BGA data structures (players, gamedatas, packets)
- [x] Compile extract.ts as standalone IIFE for MAIN world injection
- [x] Build background.ts service worker: handle icon click, inject content script, receive extracted data
- [x] Implement full pipeline in background: processRawLog -> GameState.processLog -> serialized state
- [x] Store results for side panel consumption, open side panel, send data via chrome.runtime messaging
- [x] Add badge feedback (extracting/success/error) matching current behavior
- [x] Write tests for pipeline orchestration with mocked extraction data

### Task 6: Side Panel with Summary and Downloads

**Files:**
- Create: `src/sidepanel/sidepanel.html`
- Create: `src/sidepanel/sidepanel.ts`
- Create: `src/sidepanel/sidepanel.css`
- Create: `src/render/summary.ts`
- Create: `src/render/config.ts`

- [x] Define section config as typed Record with `{ column: number, order: number, defaultVisibility, defaultLayout }` per section
- [x] Build summary renderer: GameState -> HTML string using template literals (no intermediate DTO layer)
- [x] Render card grids: base cards 2x3 CSS grid, cities cards 2x2 grid, unknown cards with age/set badges
- [x] Port summary.css: dark theme, card colors, grid layouts, multi-column page layout
- [x] Implement visibility toggles (none/all/unknown) and layout toggles (wide/tall)
- [x] Implement tooltip system: mouse-follow positioning, card image tooltips, text tooltips for cities
- [x] Reference sprites and icons via chrome.runtime.getURL()
- [x] Add download toolbar: game_log.json, game_state.json, summary.html (self-contained with inlined CSS)
- [x] Wire up chrome.runtime.onMessage to receive data from background and trigger render
- [x] Write tests for summary rendering output, toggle state management, config handling

### Task 7: Verify Acceptance Criteria

- [x] Manual test: extract data from a live BGA Innovation game, verify summary in side panel
- [x] Manual test: verify download buttons produce valid game_log.json, game_state.json, and self-contained summary.html
- [x] Manual test: verify visibility/layout toggles and tooltips
- [x] Run full test suite: `npm test`
- [x] Run linter: `npm run lint`
- [x] Verify test coverage meets 80%+
- [x] Remove Python source (src/bga_tracker/), server files, scripts/fetch_full_history.js, templates/
- [x] Remove pyproject.toml, requirements.txt, and other Python-only config
- [x] Update .gitignore for Node/TypeScript project
- [x] Update README.md with new setup instructions (npm install, npm run build, load extension)
- [x] Update CLAUDE.md with new project conventions
- [x] Move plan to docs/plans/completed/
