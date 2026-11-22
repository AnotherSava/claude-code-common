---
title: Whether a repo's docs carry screenshots is SCREENSHOTS in .claude/repo-flags
asks: never
---

## What changed

A repo used to say whether its documentation carries screenshots in its `CLAUDE.md` prose, which only an
agent reading the whole file could find, and which `/wrap-up` could not read before deciding to start
`/screenshot-relevance`. That answer now lives in one committed line, `SCREENSHOTS=yes` or `SCREENSHOTS=no`
in `.claude/repo-flags`, read and written by `~/.claude/skills/shared/repo_flags.py`.

The value alone decides it. `no` turns off every screenshot pass and offer. `yes` runs all of them, public
or private repo; the old default of skipping the missing-shot pass in a private repo is gone. A repo with no
value is asked: `/wrap-up` puts the question in its summary and records the answer.

Other screenshot guidance in a `CLAUDE.md`, such as which source trees own the strings in a frame or what a
staged demo may show, stays there. Only the yes-or-no moves.

## Migrating an existing repo

1. **Find the rule.** Read the project `CLAUDE.md` — `.claude/CLAUDE.md` where it exists, otherwise the one
   at the repo root — for a passage that rules screenshots out of the documentation, or one asking for the
   missing-shot pass although the repo is private. Guidance about how to take or check a screenshot is
   neither; leave it.
2. **Record the value.** From the repo root, run
   `python ~/.claude/skills/shared/repo_flags.py set . SCREENSHOTS no` for a ban, or the same command
   ending in `yes` for a request for the pass. Then
   `python ~/.claude/skills/shared/repo_flags.py get . SCREENSHOTS` must print the value just set.
3. **Delete the passage from `CLAUDE.md`.** What is lost is any reason it gave beyond the rule itself, such
   as when or why the decision was made. Where it gives one, move that reason into a project memory file
   before deleting, and point the memory at the flag.
4. **Commit `.claude/repo-flags`, the `CLAUDE.md` edit and any memory file together**, so no commit holds
   the rule in both places or in neither.

## When it does not apply

- **No project `CLAUDE.md`** exists at either location.
- **The `CLAUDE.md` says nothing about whether the docs carry screenshots**, settled by reading it in step 1.
  The repo then has no value, and the next `/wrap-up` asks for one.
- **`.claude/repo-flags` already holds a SCREENSHOTS value**, recorded when `/wrap-up` asked before this
  version was adopted. That answer is newer than the `CLAUDE.md` passage, so step 2 is skipped and the value
  stays; steps 3 and 4 still remove the passage.

## Continuing rule

None — this is a one-time migration. `repo_flags.py` refuses a malformed `.claude/repo-flags` whenever a
skill reads it.
