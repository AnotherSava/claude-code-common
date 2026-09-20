---
name: feedback_probe_command_still_writes
description: A command re-run just to read its output still performs every write it does — one such re-render replaced a full cache with an empty one
metadata:
  type: feedback
---

**A command re-run purely to inspect its output performs every write it normally performs.** Before re-running one as a probe, list what it persists, and check what it will persist *given the inputs you are about to hand it* — which for a probe are usually empty or throwaway.

**Why:** the mutation is invisible in the thing you came to look at. Real case 2026-09-19: `repos-status.py --report` renders a table and, as a side effect, rewrites the description cache on both machines. Checking a table-layout change meant running it with nothing on stdin; the layout rendered correctly and a twelve-entry cache was replaced with an empty one, silently. It surfaced an hour later as `0 reused from the cache` on an unrelated run, and every description had to be written again from the detail sections.

The shape generalises past caches: a renderer that also writes a manifest, a report command that stamps a last-run row, a `--dry-run` covering only half the writes. What makes it bite is that the output you came for looks right, so nothing prompts you to check anything else — the same confident pass as [[feedback_reversible_over_backup]], arriving through a command you did not think of as a writer.

**How to apply:**
- Read the command's own `Modes:` block, `--help`, or `main()` for what it writes, before using it as a probe.
- Prefer calling the pure part directly — import the renderer — or point the command at throwaway output paths. Here `--cache`, `--state` and `--html` all existed and would have cost nothing.
- Where the tool offers no such flag, snapshot what it writes first, so the probe is reversible.
- Feeding a write-through command empty input is the dangerous case, because "write what I was given" and "write nothing" are the same call.

Related: [[feedback_reversible_over_backup]], [[feedback_not_run_is_not_pass]].
