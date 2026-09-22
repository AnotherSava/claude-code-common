---
created: 2026-09-21 17:01:14
---

# Replace the plan-archive hook with a step in the commit skill

The `done` subcommand of `plan-archive.py` fires on every `Notification[idle_prompt]` and globs
every `.md` under a repo's `docs/plans/`, so it cannot tell a plan it placed there itself from a
file the repo tracks upstream.

Observed 2026-09-21 in the agwinterm clone — a third-party repo where nothing local should land.
Seconds after a `git reset --hard` restored it, the hook moved an upstream-tracked plan doc into
`docs/plans/completed/`. From its own log:

    done_moved  src: docs\plans\2026-07-31-lite-diagnostics-logging.md
                dst: docs\plans\completed\2026-07-31-lite-diagnostics-logging.md
                reason: all_tasks_checked=37

Eleven more upstream-tracked plan docs in that same run were held back only by
`NO_SIGNAL_MIN_AGE_SEC`, so they archive themselves once seven days pass. The move happens between
turns, which is why it presents as a tracked file vanishing with nothing in the transcript to
explain it.

The idea: retire the hook and archive completed plans as a step in `/commit` instead. That flow
already has the diff in front of it, already knows whether the repo is ours to write to, and would
turn a surprise working-tree mutation into a reviewed part of a commit. It also removes a
per-prompt hook, which `feedback_no_per_prompt_hooks` argues against.

Note the script has a second entry point, `start` on `PostToolUse[ExitPlanMode]`, which files a
freshly approved plan into `docs/plans/`. Whoever picks this up decides whether that moves too or
stays a hook.
