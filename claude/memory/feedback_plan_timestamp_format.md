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

**Say when a plan is finished — the hook cannot guess it.** `plan-archive.py done` also archives plans automatically, but only on a signal the plan states itself. It reads, in order:

1. An explicit `<!-- plan-archive: done -->` marker anywhere in the body — archives regardless of anything else.
2. A task list: any open `- [ ]` means in flight, leave it; all boxes `- [x]` means finished, archive.
3. Neither marker nor checkboxes: no verdict to read, so it waits until the file has been untouched for 7 days.

So a plan carrying a verification checklist stays in `docs/plans/` until those boxes are ticked — tick them as the work lands, or add the marker for a prose plan with nothing to tick. Skips are logged to `~/.claude/plan-archive.log` with a reason (`open_tasks=10`, `no_signal_age=…`), which is where to look if a plan archives or lingers unexpectedly.

Until 2026-08-19 the hook instead inferred completion from the session going idle without a trailing `?` — unrelated to whether any work happened, and it archived a plan four minutes after it was written, before a single step ran. Idleness now only decides *when to look*, never whether to move. Nothing is lost by a skip: the check runs on every idle prompt, so a plan archives at the first idle moment after it says it is done.
