# Regrouping a pushed history into fewer logical commits

A stretch of review-driven work leaves a history nobody can read later: fix, fix-the-fix, revert half
of it, lint. The net change usually packs into a handful of commits by theme, but splitting it by
resetting and hunk-staging in the working tree is fragile. Each intermediate commit has to build on its
own, and nothing checks that until someone bisects. The method below builds every intermediate commit as a
tree object first, gates each one, and only then turns the trees into commits. The main working tree and
`main` stay untouched until the last step. Measured 2026-09-27 on a .NET repo, where 35 pushed commits
became 13.

## Record the target tree first

Turn the finished working tree into a tree id with a scratch index, and compare every later step against
it:

```bash
export GIT_INDEX_FILE="$PWD/tmp/target.idx"
git read-tree HEAD && git add -A && git write-tree   # prints the target tree id
unset GIT_INDEX_FILE
```

The last regrouped tree must equal this id byte for byte. That one comparison proves no hunk was lost or
invented in the split.

## Split the net diff into per-commit file states

Define the commits first: an ordered list, each with a scope a reviewer can check a hunk against. Then
walk `git diff <base> <target>` file by file:

- **A file only one commit changes** takes its final content at that commit. There is nothing to write.
- **A file several commits change** gets its content as it stands after each of them except the last,
  written to `states/<n>/<path>`: base plus every change of commits up to `n`, each change in its final
  form. The last commit's state is the target's content.

Read both ends with `git show <base>:<path>` and `git show <target>:<path>`, never the working-tree copy.
Its line endings can differ from the stored blob, and a state built from it carries them in. This split is
the work that parallelises: one agent per group of files, each writing states and noting cross-file
dependencies ("commit 5 needs the helper commit 3 adds").

## Build each commit's tree without committing

Per commit `k`, build a scratch index from the base, overwrite each file with its state after `k`, and
write a tree:

```bash
export GIT_INDEX_FILE="$PWD/tmp/idx-$k"
git read-tree <base>
blob=$(git hash-object -w --no-filters states/$m/$path)       # or the target's blob at the file's last commit
git update-index --add --cacheinfo 100644,$blob,$path          # --force-remove for a file gone by then
git write-tree
```

Use `--no-filters` because the states are already the bytes git stores. The base's `.gitattributes` may
predate an `eol` rule the target added. Leave transcrypt-encrypted paths out of the split entirely, and let
them ride along from the base index. They are plaintext in the working tree, so `hash-object --no-filters`
on one would store the plaintext unencrypted.

## Gate every tree in a worktree outside the repo

Create a detached scratch worktree beside the repo, not inside it, and check each tree out there with its
own gate:

```bash
git worktree add --detach ../repo-scratch <base>
git -C ../repo-scratch read-tree -u --reset <tree-k>
( cd ../repo-scratch && bash .claude/commit-checks.sh )
```

Keep it outside the repo, or every intermediate tree is gated under the final tree's rules. MSBuild
searches parent folders for `Directory.Build.props`, and so does the lookup for `.editorconfig` and
`global.json`, so a worktree under the repo's own `tmp/` inherits the target's analyzer config and SDK pin
at commits that predate them. A gate step that reads machine state keyed by the checkout path fails at the
scratch path for reasons unrelated to the tree. A per-repo memory link is one example; run that step
separately and say so.

When a gate fails, move the offending change to an earlier or later commit by editing the states, rebuild
from the earliest tree affected, and never touch the target content.

## Review every commit against its definition

Have a reviewer read each `git diff <tree k-1> <tree k>` hunk by hunk against the commit's scope. The
lint commit needs it most. A plan filed six behaviour changes as "mechanical lint edits", and all six read
that way in the diff:
- a silent catch that started logging
- a log level raised
- a culture-invariant parse
- a new fallback rectangle
- a swallowing try removed
- a widened catch

Moving them gave two new fix commits, so budget a second build-and-gate pass.

## Turn the trees into commits, then push

Only after the commit messages are approved:

```bash
prev=<base>
for k in 1..N:  prev=$(git commit-tree <tree-k> -p $prev -S -F msg-$k.txt)
git reset $prev    # the working tree already equals this tip: nothing on disk changes, status is clean
git push --force-with-lease=main:<old-tip> origin main
```

The lease fails rather than overwrites if anything else reached the branch after the old tip. Auto mode's
classifier denies that push even after the user approves it, so plan on handing the user the exact command
(see `claude-code-auto-mode-permissions.md`). Screenshot manifests, memos and anything else that cites a
commit hash from the old history need repointing at a commit that survives. Pointing them at the tip they
are committed in is impossible.
