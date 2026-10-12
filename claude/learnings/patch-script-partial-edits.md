# A patch script that asserts mid-way writes nothing, and re-running the remainder ships half an edit

Editing a file through a short script — a python heredoc doing several `s.replace(old, new)` with an
`assert old in s` before each, then one `write_text(s)` at the end — is the right shape for a multi-part edit.
It has one failure mode, and the expensive part is not the failure itself.

## What happens

```python
s = p.read_text()
s = s.replace(FIRST_OLD, FIRST_NEW)      # applied, in memory
assert SECOND_OLD in s                    # fires: the anchor had a stray character
s = s.replace(SECOND_OLD, SECOND_NEW)
p.write_text(s)                           # never reached
```

The traceback names the *second* anchor, so it reads as "one of two edits failed". Nothing was written at all,
and the first edit is gone with the interpreter. Then the natural next move — re-run a script containing only
the part that failed — applies the second edit to a file that never received the first, and the file is now in a
state neither version intended.

Measured 2026-10-11 on a database sync script: the first replacement changed a fingerprint to print one digest
per collection, the second changed the comparison to read them. The assert fired on the second, nothing was
written, and the follow-up script applied only the comparison — leaving a script that compared a `digest` line
the fingerprint no longer printed. `bash -n` passed it, because the file was syntactically perfect, and the
first real run failed with *read no digest from production*, which points at the remote rather than at the edit.

## What to do instead

- **Assert every anchor before the first replacement.** One pass to check, one pass to replace. Then a bad
  anchor costs nothing and the message names it before anything is in memory.
- **Print what was written.** A script that ends with `print('written')`, or with the count of replacements
  made, makes "nothing was written" visible rather than inferred from the absence of a traceback.
- **After any partial failure, verify the halves you believe are in place** — `grep` for both new strings —
  rather than re-running the remainder. Which edits reached disk is the question, and the traceback does not
  answer it.
- **A syntax check is not a consistency check.** `bash -n`, `python -m py_compile` and a type-checker all pass a
  file whose two halves disagree. Run the thing the file feeds: the sync above needed one real invocation, and
  `~/.claude/memory/feedback_validate_self_gating_edits.md` makes the same point for files that gate their own
  edits.

## When the file is small enough

Edit tools do not have this failure: each `Edit` call either applies and is durable or fails and changes
nothing, so a sequence of them cannot half-apply. Reach for a script when the edit is repetitive or the anchors
are long, and accept that doing so buys back the atomicity problem the tools removed.
