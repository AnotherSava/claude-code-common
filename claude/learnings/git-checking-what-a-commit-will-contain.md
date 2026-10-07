# Asking git which files a check should read

A check that inspects a repo to decide whether something is present — a convention rule, a lint gate, a
"does this project still declare X" assertion — is normally run by a commit flow. That flow empties the
index first, on purpose, so that the diff it builds a message from cannot describe a half-staged tree. The
obvious instrument for "which files does this repo have" then answers about the *previous* commit rather
than the one being made, and it answers with no error.

`git ls-files` lists the index. A tracked file the change set modifies still appears, because `HEAD` put it
there. A file the change set **adds** appears only while it is staged, so it vanishes the moment anything
unstages — and `/commit` runs `git reset HEAD` among its context probes, before it runs the project's gate.
Every new file in the change set is therefore invisible to a check reading `--cached` at the one moment the
check actually runs.

Which *repo* the check is in is the separate question, answered in
`git-identifying-the-repo-a-check-is-in.md`; `ports-from-registry` had both defects at once.

## Ask for what the repo would commit

```bash
git ls-files -z --cached --others --exclude-standard -- <pathspec>
```

That is the set git itself would put in a commit: the index, plus untracked files, minus everything an
ignore rule hides. It does not depend on whether anyone has run `git add` yet, which is what makes a
verdict reproducible across the staged, unstaged and reset states a commit flow moves through.

`--exclude-standard` is why this beats walking the directory. The reason a check reaches for tracked-only in
the first place is usually sound — a `package.json` inside `node_modules/`, a manifest inside a virtualenv,
a `.gitignore` written by an IDE are nobody's declaration and must not count. Every one of those is
*ignored*, not merely untracked, so the flag excludes them while still seeing the file a migration just
wrote. Tracked-vs-untracked was never the distinction that mattered; ignored-vs-not was.

## Both directions fail silently, and one of them is worse

Two rules in `claude/conventions/rules/` read `--cached` alone, and they failed opposite ways:

- **Failing closed** is loud enough to be found. `ports-from-registry` asks whether a launch-determining
  file resolves the repo's port from the registry. The migration that satisfies it adds `scripts/dev.mjs`;
  the reset un-staged it; the rule reported that nothing resolves the port and instructed the reader to copy
  in a file already sitting in `scripts/`. Someone hit that, could not reconcile the advice with the tree,
  and reported it.
- **Failing open** is the one nothing reports. `gitignore-scope-global` asks which `.gitignore` files the
  repo owns, to check none repeats a line belonging in the global excludes file. A `.gitignore` *created* by
  the change set is read by nothing, so the rule examines zero files and the gate prints a pass. A first
  `.gitignore` carrying `.idea/` would have gone in unreported.

A check that cannot see a new file is not a check with reduced coverage — it is a check whose silence means
nothing, on exactly the commits that introduce the thing it looks for.

## Test for it in three states

The tell is a verdict that moves when nothing about the repo's content does. Run the check against one
scratch repo in all three states and require the same answer:

```bash
# the file on disk, never added
git -C "$repo" status --short            # shows it as untracked
# staged, as a migration's own instructions usually leave it
git -C "$repo" add -- scripts/dev.mjs
# and after the unstage a commit flow performs before running the gate
git -C "$repo" reset HEAD --quiet
```

Add a gitignored file matching the same pathspec — a `node_modules/package.json` holding a plausible port,
say — and require that it stays excluded in all three. That half is what stops the fix from becoming a
directory walk that counts a virtualenv's manifest as the project's own.

A migration's prose is the other place this leaks. One convention version told the adopting agent to
`git add` the new file before re-running the check, with the reason written out: the check reads tracked
files. That instruction is a workaround for this defect wearing the clothes of a requirement, and it
survived in the README until the rule was fixed. A step that tells a reader to stage something so a checker
will see it is a report of this bug.
