---
title: The agent's tmp/ is ignored by the global excludes file, not by each repo
---

## What changed

The agent writes everything it has to read back — contact sheets, logs, previews — into a `tmp/`
folder at the root of whichever repo it is working in. That folder belongs to how the agent works
rather than to any project, so the global excludes file (`git/gitignore` in the dotfiles repo) now
ignores `/tmp/` once for every repo, and a project `.gitignore` no longer carries its own copy.

A repo that kept the line now fails its commit gate: v2's `gitignore-scope-global` rule re-reads the
global file at every commit and reports the project's `/tmp/` as a duplicate. This version is the
migration that clears it.

## Migrating an existing repo

Fetch first, and do not run this on a branch behind its upstream: the edit is to a committed
`.gitignore` the other machine may have changed.

1. **Confirm this machine has the new global file.** Run
   `git config --global core.excludesfile` and check the file it names contains a `/tmp/` line. If it
   does not, pull the dotfiles repo first — without it, deleting the project line leaves `tmp/`
   visible to `git status`, and the next `git add .` stages scratch files.
2. **Delete the line.** In the root `.gitignore`, remove the `/tmp/` line, along with any comment
   above it that explains only that line. A comment that also covers neighbouring lines stays, edited
   so it no longer mentions `tmp/`.
3. **Check the result.** `git check-ignore -q --no-index tmp/x` must exit 0, now answered by the
   global file, and `python ~/.claude/conventions/check.py .` must report no `gitignore-scope-global`
   finding.

Leave two lookalikes alone, because neither is a duplicate and the gate does not report them:

- `tmp/` with no leading slash hides a `tmp/` at every depth, which is a decision about the
  project's own layout.
- A `/tmp/` line in a nested `.gitignore` is anchored to that directory, which the global entry does
  not reach.

Files already tracked under `tmp/` stay tracked; an ignore rule never untracks anything.

The deletion costs one thing: someone who clones the repo without this setup's global excludes file
sees `tmp/` as untracked. Only the agent writes to that folder, and the agent runs where this setup
is installed, so a clone elsewhere has nothing in it to stage.

## When it does not apply

The root `.gitignore` holds no `/tmp/` line — `grep -nx '/tmp/' .gitignore` prints nothing — or the
repo commits no root `.gitignore` at all.

## Continuing rule

None — this is a one-time migration. v2's `gitignore-scope-global` already reports the line in any
repo at v2 or later.
