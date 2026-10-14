# Snapshotting a dirty working tree to see what a command changed

A tool that runs something in a user's repo (a build, a formatter, a generator) and must report or undo what it
wrote cannot assume a clean tree. The user's own uncommitted edits are already there, and the obvious
comparisons miss exactly the files that are. Everything below was reproduced in scratch repos on 2026-09-26
with git 2.39 in Git Bash on Windows.

## What does not work

- **Comparing `git status --short` before and after.** A tracked file the user already modified reads ` M`
  both times, however many times the command rewrites it. A file the command creates inside an untracked
  directory is folded into the `?? dir/` line that was already there, unless you pass `-uall`.
- **`git stash create` as the snapshot.** It prints a commit capturing tracked changes and touches nothing,
  which looks ideal. But it never includes untracked files, so an untracked file the command rewrites can be
  neither detected nor restored from it. It also prints nothing when no tracked file has changed, whether the
  tree is clean or holds only untracked files. `HEAD` then stands in as the snapshot.

## What does: a tree written through a scratch index

```sh
GIT_INDEX_FILE=/tmp/snapshot-myrepo git add -A
GIT_INDEX_FILE=/tmp/snapshot-myrepo git write-tree
```

The second command prints a tree id covering every file git does not ignore, tracked or not, and the real
index is untouched. Take one before the command and one after, and then:

- `git diff --name-status <before> <after>` names every file the command changed, created or deleted. That
  includes a second write to an already-modified file and a write to an untracked one.
- `git restore --source=<before> --worktree -- <path>` puts a file back as it was before the command,
  including the user's own pending edit, and including a file that was untracked. A file absent from
  `<before>` was created by the command and is deleted instead.

The traps in it, each reproduced:

- **Seed the scratch index, or a tracked file that matches an ignore pattern is invisible.** An empty index
  applies the ignore rules to every path, so a force-added file under an ignored directory never enters
  either tree. Its rewrite then goes unreported, although `git status` shows it modified. Copy the real index
  first, once: `cp -p "$(git rev-parse --git-path index)" /tmp/snapshot-myrepo`.
- **Keep the copy's modification time.** Git re-hashes a file only when its mtime is not older than the
  index's, so a plain `cp` (or Python's `shutil.copyfile`) stamps the copy "now" and hides any edit made in
  the same tick as the last real index write. A same-size edit then enters the snapshot as its old content.
  Use `cp -p` or `shutil.copy2`. Measured October 2026 on Windows: a test editing a file right after a commit
  recorded the stale blob in 5 of 20 runs with `copyfile` and 0 of 20 with `copy2`. To make the race fire on
  every run, backdate the file before committing it (otherwise the commit marks the entry racy and git
  re-hashes it anyway), then after the same-size edit set the file's and the index's mtime to that one instant.
- **Name the scratch index per repo.** Two runs sharing one path race. A second repo's `add -A` between the
  first repo's `add -A` and `write-tree` makes `write-tree` fail with `invalid object`. A second repo's
  cleanup in that gap makes `write-tree` silently print the empty tree `4b825dc6`, and every file then reads
  as deleted.
- **Ignored paths are outside the snapshot entirely.** A command that empties `node_modules/` or rewrites a
  gitignored config changes nothing either tree can show.
- **Delete the scratch index by a literal path.** Claude Code's removal check refuses `rm` on a path computed
  at run time; see `claude-code-auto-mode-permissions.md`.

Changes made by anything else while the command runs, such as an editor saving a file or another session
writing, land in the same diff. So restore on a person's yes rather than automatically.
