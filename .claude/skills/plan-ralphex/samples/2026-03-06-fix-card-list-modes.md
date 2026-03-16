# Fix card list modes (All / Unknown)

## Overview

The base-list and cities-list sections render unresolved cards as gray face-down placeholders (age only). This breaks both "All" mode (should show every card face-up) and "Unknown" mode (should show unresolved cards face-up while masking resolved ones). The fix is a one-line change in `prepareAllCards` — render all cards via `renderKnownCard` instead of falling back to `renderUnknownCard` for unresolved ones. The existing CSS for `.mode-unknown` already handles masking `[data-known]` cards correctly.

## Context

- Files involved: `src/render/summary.ts`, `src/__tests__/sidepanel.test.ts`
- The `prepareAllCards` function (summary.ts:301) builds rows for the card catalog lists
- Currently: resolved cards → `renderKnownCard(info, true)`, unresolved → `renderUnknownCard(info.age, info.cardSet)`
- The CSS `.mode-unknown [data-known]` rules already hide content of resolved cards; `.mode-unknown .all-known` hides fully-resolved age rows
- No CSS changes needed — the existing styles work correctly once the HTML renders all cards face-up

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Single-task fix; minimal change
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Implementation Steps

### Task 1: Render all catalog cards face-up

**Files:**
- Modify: `src/render/summary.ts`
- Modify: `src/__tests__/sidepanel.test.ts`

- [x] In `prepareAllCards` (summary.ts line 310), replace `resolved ? renderKnownCard(info, true) : renderUnknownCard(info.age, info.cardSet)` with `renderKnownCard(info, resolved)` — this renders every card face-up, marking resolved ones with `data-known`
- [x] Add test: in "All" mode, unresolved cards in base-list render with card name visible (not as gray placeholders)
- [x] Add test: in "Unknown" mode, resolved cards have `data-known` attribute (already exists, verify still passes)
- [x] Run project test suite — must pass

### Task 2: Verify acceptance criteria

- [x] Manual test: open side panel, toggle base-list to "All" — all 50 base cards show face-up with icons and names
- [x] Manual test: toggle to "Unknown" — resolved cards appear as blank gray boxes (no age), fully-resolved age rows hidden, unresolved cards show face-up
- [x] Run full test suite (`npm test`)
- [x] Run linter (`npm run lint`)

### Task 3: Update documentation

- [x] Update CLAUDE.md if internal patterns changed
- [x] Move this plan to `docs/plans/completed/`
