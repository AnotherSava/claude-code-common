---
title: The shared screenshot machinery is called from the screenshot skill, not docs-relevance
---

## What changed

A capture script in a project calls shared tools by their path under `~/.claude` — the shutter, the
frame and edge steps, the contact-sheet builder, the Windows capture library and the checker that
resolves it. Those tools moved with the procedure that uses them. Taking, framing, filing and showing a
screenshot is now its own `screenshot` skill, so that it loads whenever a picture is taken rather than
only inside a `docs-relevance` run, and the machinery went with it:

- `~/.claude/skills/docs-relevance/scripts/` is now `~/.claude/skills/screenshot/scripts/`, file names
  unchanged.
- `contact-sheet.html` and `screenshot-manifest.md` are now under `~/.claude/skills/screenshot/references/`.
- `window_list.swift` is gone. DocShot's `--list` lists windows inside the bundle that holds the Screen
  Recording grant; `swift window_list.swift` depended on the calling terminal holding that grant, and a
  rebuilt ad-hoc-signed terminal can show the switch on while every window title comes back blank.

`docs-relevance` keeps deciding whether a frame is stale and whether its `policy` permits a replacement,
and hands the capture to `screenshot`.

Nothing in a caller's tree reports the old path going away: the path is a string, and a capture script
runs only when someone re-shoots, so the failure waits until a window is staged and the shutter fires.
`learnings/skill-scripts-as-a-dependency.md` has the measured case.

## Migrating an existing repo

Do this in the repo that is behind. Fetch first and do not run it on a branch behind its upstream: the
work edits committed capture code the other machine may also have changed.

1. **Find every reference.** Run `git grep -n -e 'docs-relevance' -e 'window_list'` and read every hit.
   The path is assembled differently in each kind of file, so a hit on the bare skill name is what
   catches them all: a Python `Path.home() / ".claude" / "skills" / "docs-relevance" / "scripts"`, a
   PowerShell `Join-Path $env:USERPROFILE '.claude\skills\docs-relevance\scripts\…'`, a shell
   `~/.claude/skills/docs-relevance/scripts/…` in a commit gate.
2. **Repoint each path.** Change `skills/docs-relevance/scripts` to `skills/screenshot/scripts`, and
   `skills/docs-relevance/references` to `skills/screenshot/references`, in whichever separator the file
   uses. A prose mention of the skill as the owner of the shared tools — a comment, a manifest `steps`
   note saying a frame was drawn by "the docs-relevance skill's `winframe.py`" — names the `screenshot`
   skill instead. Leave alone a mention of `docs-relevance` as the staleness check, and anything under
   `.claude/memos/done/`, which records what was true when it was closed.
3. **Replace a `window_list.swift` caller.** List windows through DocShot instead:
   `open -g -n -W -a ~/Applications/DocShot.app --args --list --out <file>`, then read the JSON from
   `<file>`. DocShot has to be launched through `open` for its grant to apply, which is why the result
   comes back in a file and not on stdout. The rows differ from `window_list.swift`'s in three ways a
   caller has to absorb: the size keys are `width` and `height` instead of `w` and `h`, there is no
   `pid`, and the exit status is 3 when the grant is missing. A repo that never called it has nothing
   to do here.
4. **Run what checks the paths.** Run the repo's commit gate. Where it does not already do so, and the
   repo's Windows captures dot-source `windows-capture.ps1`, also run
   `pwsh -NoProfile -NonInteractive -File ~/.claude/skills/screenshot/scripts/check-capture-scripts.ps1`
   from the repo root. Then rerun the step 1 search: what it prints now should be only the mentions
   step 2 chose to keep.

None of this deletes or rewrites anything the repo cannot regenerate; the edits are path strings and
comments.

## When it does not apply

- `git grep -n -e 'docs-relevance/scripts' -e 'docs-relevance\\scripts' -e 'docs-relevance/references' -e 'window_list' -e '"docs-relevance" / "scripts"'`
  prints nothing outside `.claude/memos/done/`. Check that the patterns can find a hit before trusting an
  empty result: `git grep -n 'docs-relevance'` lists every mention, and reading those lines settles
  whether one is a path the patterns missed.
- The repo is a clone of someone else's project, which adopts nothing.

## Continuing rule

None — this is a one-time migration.
