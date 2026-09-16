---
created: 2026-09-15 17:30:42
---

# audit re-derives a recorded line against whatever step now owns that version, never checking the slug

Measured 2026-09-15 in this repo, reading `conventions.py` while surveying the adopt engine for an unrelated fix. Never surfaced at the time, so it is here rather than lost.

## What it does

`cmd_audit` iterates the recorded lines and resolves each one by integer alone:

    record, step = lines[version], find_step(steps, str(version))
    head = f"  v{version:<3} {record.state:<8} {record.slug:<28}"

The head prints `record.slug` — the name stored when the line was written. The re-derivation then runs whatever step now carries that version number. The two are never compared.

## Why it can diverge

Step prose is append-only and never renumbered, so a version cannot change hands that way. A `slug:` can still change: editing frontmatter is a prose fix, and `authoring-a-step.md` says prose fixes are free. After such an edit every already-recorded line keeps the old slug and prints it, while the new step is what re-derives the verdict beside it. The output reads as a fact about the named step and is a fact about a different one.

Same shape at a second site: `cmd_record` resolves through `find_step(steps, key)` and writes `step.slug`, so re-recording silently repairs the row — which means the divergence is visible only in repos that have not been re-recorded since, and disappears the moment anyone does.

## The fix, undecided in one respect

One line of comparison in `_audit_one` or beside the head, printing a warning when `record.slug != step.slug`. What is not obvious is the verdict it should carry: it is not a `FAILED` (the shape may be perfectly fine) and it is not `ok` (the record names something that no longer exists under that number). A fourth tally bucket, or a suffix on the existing line, are both defensible.

Worth doing at the same time: decide whether `record` should print what it replaced when the slug changes, the way it already prints `(replacing applied)` for a state change.
