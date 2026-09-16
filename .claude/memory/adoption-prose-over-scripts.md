---
name: adoption-prose-over-scripts
description: why a convention version's migration is prose an agent follows rather than a script with a per-item assertion, including the case that argued hardest against it
metadata:
  type: project
---

A version's `## Migrating an existing repo` section is instructions, not code. The default is prose and an `apply.py` is the exception, because the argument for requiring a script collapsed on 2026-09-16 when it was traced through.

The hard case was v1, which turns `.claude/memos.md` into `.claude/memos/` and deletes the source. Its first draft matched one checklist line shape by regex, ignored every line it did not recognise, ran its per-item check over only the lines it had recognised, deleted the file, and reported "each asserted present exactly once" — true of the 29 it saw, while four shapes it never saw were gone. That incident is why the old design insisted the assertion be a program: a reading can be blind, and evidence produced by the pass that did the work is blind wherever that pass is.

Three facts remove the requirement, and all three had to hold:

- **The source is not destroyed.** It leaves the working tree, but the commit that deletes it carries its full text in the diff, so `git show` recovers it permanently. What the adoption commit removes is the evidence from `HEAD`, not from history.
- **A second, independent pass is available.** Checking the diff rather than the migrator's account of what it migrated is a different reading from the one that did the work, which is the property that mattered — not that a program did the checking.
- **That pass always runs before anything is committed.** `/commit` analyses the change set before it commits, so there is no committed-but-wrong state to unwind; the correction is a working-tree edit. See [[project-memory-versioning]] for the sibling case of a decision that only works because a later step already owns it.

What survives as code is the continuous half — the rules under `claude/conventions/rules/`, which run unattended in a commit gate where no agent exists. A generic completeness check (every non-blank source line appears somewhere under the destination) is still worth having for the one case with no agent in it at all: a plain `git commit -m` typed by hand.
