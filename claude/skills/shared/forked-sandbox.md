# Working in a sandbox from a forked skill

Read by `docs-relevance` and `screenshot-relevance`, which both run as backgrounded forks and both hand their caller a
patch instead of editing the user's tree. `<name>` below is the reading skill's own name.

## Working directory

Every repo path a skill names (`README.md`, `docs/`, `CLAUDE.md` and the rest) is relative to the root of the
**sandbox** step 0 creates, not to **Repo root** from the skill's Context. Those two are different directories, and Repo
root is the user's tree, which the skill must not write to — prefix the sandbox path on every Read/Edit/Write and `git`
call once step 0 has run. The Context probes were taken in the real repo before the sandbox existed, which is correct:
the sandbox is built to mirror exactly that state, so a diff quoted there describes the sandbox too.

Bare paths are resolved against the current working directory, so they are only safe after step 0's `cd` and never
before.

## Step 0: work in a sandbox, not the user's tree

Run `python ~/.claude/scripts/worktree-sandbox.py create --name <name>` and `cd` to the path it prints on its last line. That is a detached git worktree outside the repo, already holding the pending change set — the uncommitted edits, the new files, the deletions — so every step below sees exactly what the caller sees. Do all of your reading and every edit there.

Nothing this skill does reaches the user's tree, which is the point: a fork's writes land outside the session's checkpoints, so `/rewind` cannot undo them, and the caller applies a patch it has reviewed instead. Two consequences to respect. **Ignored files are not carried in** — the script says so when it runs — so a step needing a build artifact must copy it in itself rather than concluding it is absent. And a file you *create* is untracked in the sandbox and therefore absent from the patch, so `git add -N <path>` it as you go; `patch` warns on stderr about any you missed, and that warning is the one output of this flow that must never be ignored.

**Do not run the repo's commit gate or its convention checker from here, and never report a verdict from one as the repo's.** A check that asserts where the repo is installed cannot be true of a sandbox: `install-links-present` compares `~/.claude` against whichever tree it runs from, `memory-cache-linked` derives a Claude project id from the checkout path, and `ports-from-registry` reads the repo's identity to decide which port claims are its own. Each then reports a defect in a tree that has none — measured 2026-10-06, a run in a sandbox named a correctly-pinned port as a violation and said the commit gate was failing, which it was not. The caller runs that gate in the real root, at its own step; your job is the documentation. Where a documentation claim can only be settled by running such a check, flag it unverified and say which command would settle it, exactly as for a cross-repo claim. `~/.claude/learnings/git-sandbox-for-an-uncommitted-change-set.md` carries why this class exists.

When the carry-in cannot run at all — not a git repo, or the worktree add fails — say so and stop rather than falling back to editing the real tree. `/commit` treats a missing sandbox as a reason to run this skill in the main session, where the checkpointing works.

At the end, emit the patch with `python ~/.claude/scripts/worktree-sandbox.py patch <sandbox> --binary` (the flag is what carries an image change), save it inside the repo's gitignored `tmp/`, and report that path plus a plain-language summary of every file it touches. Then tear the sandbox down with the `remove` subcommand, run from the repo root rather than from inside the sandbox: Windows will not delete a directory that is any process's working directory, the calling shell's included. Report the patch path even when the patch is empty, so "nothing to fix" and "the run failed" cannot be confused.
