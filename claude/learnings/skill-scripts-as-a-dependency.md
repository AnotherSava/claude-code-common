# A skill's scripts are an API other repos call

A repo that shells out to `~/.claude/skills/<name>/scripts/…` has taken a dependency on a path
in the dotfiles repo, and nothing links the two. Renaming the skill breaks every caller at
once, in repos whose tests, CI and commit gates all stay green: the path is a string, so
nothing resolves it until someone runs the code holding it.

## What a rename breaks, and why nothing reports it

The `documentation` skill was renamed to `docs-relevance` on 2026-09-17. Both of
tauri-dashboard's screenshot capture libs — the Python one and the PowerShell one — call
`hairline.py` and `window_list.swift` through the old path, and both went on resolving it for
three days. A capture script runs only when a person re-shoots something, so the failure
waited until a window had been staged and then threw at the shutter.

Nothing in that repo could have caught it. Its own `check-figures.py` reads the committed
frames and the manifest, never the libs that produce them, and CI cannot check the paths at
all — a runner has no `~/.claude`.

The exposure is wider than capture scripts. The `deploy` skill writes each repo a
`scripts/deploy.sh` whose body is `bash ~/.claude/skills/deploy/scripts/<TARGET>`, and keeps
that wrapper out of git through the global excludes file. Renaming `deploy` would break every
repo's shortcut on every machine, with no tracked file anywhere to sweep.

## Asserting the dependency in the caller's gate

Put the check in the project's own commit gate. Three things decide whether it holds up:

- **Read the reference list out of the source, never restate it.** Grep the call sites
  (`skill_script("…")`, and whatever the other platform's lib does inline) and resolve each
  against the constant the lib itself defines. A check carrying its own copy of the list
  asserts a set the libs may already have stopped using, and that second copy is the thing the
  check exists to prevent.
- **An empty match set has to fail.** Both halves of that grep match a shape the libs chose
  and can rewrite, and matching nothing reads exactly like matching everything and finding it
  well. Exit non-zero and say the patterns went stale rather than the paths.
- **It belongs in the local gate, not the workflow.** The paths resolve under the developer's
  home directory, so a runner fails every run. That makes it one of the rare checks
  deliberately absent from CI, which is worth a comment where it sits — the default assumption
  on reading a gate script is that everything in it mirrors a workflow.

The worked example is `docs/screenshots/check-skill-scripts.py` in the tauri-dashboard repo.

## Sweeping the callers when you rename a skill

That gate is the caller's half, and it speaks only after the break. The rename itself happens
in the dotfiles repo, so sweep from there: grep the other checkouts for `skills/<old-name>`
and fix what it finds in the same pass. It will not find the per-machine wrappers, which are
gitignored on each machine — regenerate those by re-running the skill that writes them.
