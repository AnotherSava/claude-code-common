---
name: Plan file timestamp format and lifecycle
description: When saving a plan into docs/plans/, prefix with YYYY-MM-DD_HH-MM; move to docs/plans/completed/ once execution finishes.
type: feedback
---

When saving a plan — or any similar dated document — into a project's `docs/` folder (e.g. `docs/plans/`), prefix the filename with the current timestamp in **`YYYY-MM-DD_HH-MM`** format.

Example: `docs/plans/2026-04-19_18-43-electron-to-tauri-migration.md`

After the plan has been fully executed, **move** the file from `docs/plans/` into `docs/plans/completed/`. Do not rename it — keep the original timestamped filename so the archive reads as a chronological record.

**Why:** The date-only format used historically (e.g. `2026-04-19-foo.md`) loses ordering within a day — multiple plans created on the same day collide alphabetically. Time-of-day preserves authorship order. Keeping in-flight plans separate from completed ones (via the `completed/` subfolder) makes it easy to see what's still active.

**How to apply:**
- When creating a plan doc: format the date prefix as `YYYY-MM-DD_HH-MM-<slug>.md`. Use the user's local time (what `date +"%Y-%m-%d_%H-%M"` returns). Use hyphens between the timestamp and the slug.
- When execution of the plan is complete (all stages/tasks done): `git mv docs/plans/<file>.md docs/plans/completed/<file>.md` — keep the same filename.
