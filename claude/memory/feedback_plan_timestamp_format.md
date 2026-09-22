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
- The first `# H1` heading inside the plan body must be a descriptive title (e.g. `# Refactor X to Y`). The `plan-archive` hook derives the filename slug from this H1; generic section headers like `# Context` or `# Plan` produce useless archived filenames. Keep section headings at `##` under the title.

**Say in the plan when it is finished — nothing else can tell.** The `commit` skill makes the move, reading two signals out of the body with fenced code blocks stripped, so a checkbox quoted in an example is not mistaken for the plan's own state:

1. An explicit `<!-- plan-archive: done -->` marker anywhere in the body — finished, whatever else the file says.
2. A task list: any open `- [ ]` means in flight and it stays put; at least one `- [x]` with no open boxes means finished.

A plan carrying neither states no verdict, and `/commit` reports that rather than guessing from its age. So a plan with a verification checklist sits in `docs/plans/` until those boxes are ticked — tick them as each piece is done, or add the marker for a prose plan with nothing to tick. The move is proposed in the commit plan and made only on confirmation, which puts it in the same commit as the work it describes.

A `completed/` folder predating 2026-09-21 may hold a plan nobody ever finished, and a repo you only read from may be missing one: an idle-prompt hook used to make this move unattended, and it globbed every `.md` under `docs/plans/` with no way to tell a plan it had filed itself from a document the repo tracks upstream.
