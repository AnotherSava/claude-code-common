---
title: Raw screenshot captures are committed, and kept off the site
rules: screenshot-raws-unpublished
---

## What changed

Every framing step in the docs-relevance skill edits a screenshot in place — `hairline.py` grows or
traces a ring, `winframe.py` redraws a Windows frame — so the untouched capture is the only input
from which a frame can be made again with different settings. It used to be kept in the repo's
gitignored `tmp/`, which exists on one machine only, and the next capture of the same name
overwrote it. Re-framing on the other machine, or after a re-shoot, meant taking the picture again,
which needs the app staged and the machine taken over.

The raw is now committed beside the frame, at `docs/screenshots/raw/<name>` with the same file name
as the frame it produced. `Add-WindowFrame` in the skill's `windows-capture.ps1` writes it there. A
re-capture overwrites it in the working tree, and git keeps the one before.

That directory sits under `docs/`, and Jekyll publishes every file under `docs/` it is not told to
leave out. So a repo that commits raws also excludes them from its site, or each one goes live
beside the frame made from it.

## Migrating an existing repo

Fetch first, and do not run this on a branch behind its upstream: the work edits
`docs/_config.yml` and capture code, committed files the other machine may have changed
(`learnings/git-stash-pull-safety.md`).

1. **Keep the raws off the site.** In `docs/_config.yml`, add `screenshots/raw/` to the top-level
   `exclude:` list, with a one-line comment above it saying these are inputs to the frame step and
   not pages. Where the list exists, append to it and touch nothing else. Where there is none, add
   one holding only this entry, and confirm the next Pages build still succeeds before believing it.
   A repo whose site is not Jekyll, or whose `docs/` is not the published source, is a question for
   the user: name what publishes the docs and ask where the exclusion belongs.
2. **Point the capture code at the new directory.** Search `docs/screenshots/capture/` for where it
   keeps raws — `tmp/raw`, `tmp/screenshot-raws`, a `keep_raw` helper, or any copy made before a
   frame step. Change each to write `docs/screenshots/raw/<frame file name>`, the same name as the
   frame rather than a `.raw.png` stem. The raw is the file as it stands just before the frame step
   (`hairline.py` or `winframe.py`), after every crop, trim or colour conversion, so where a helper
   copies earlier — tauri-dashboard's `keep_raw` runs inside `capture_window` for every capture,
   before its halo trim and sRGB conversion — move the copy to just before the frame step, and keep
   it only when that step's output is the committed frame under `docs/screenshots/`, never for a
   probe or an intermediate capture written to `tmp/`. Where the capture code frames in place and
   copies nothing first — a project-local border or frame helper that saves over its input, such as
   achievement-overlay's `docborder.py` or bga-assistant's `border.py` — add that copy before it,
   creating the directory when it is missing and failing loudly when the copy fails. A capture that
   frames only through `Add-WindowFrame` needs nothing: the shared function already writes there. A
   capture with no frame step needs nothing either, because the committed file is its own raw.
   Afterwards run whatever the repo's commit gate runs over its captures, including — on Windows,
   from the repo root — `~/.claude/skills/docs-relevance/scripts/check-capture-scripts.ps1` where the
   capture scripts dot-source the skill's `windows-capture.ps1`. Captures built on a library of their
   own, as achievement-overlay's are, give it nothing to check, and it fails on them.
3. **Bring over the raws this machine already holds.** Look in `tmp/screenshot-raws/` and
   `tmp/raw/`. A frame whose capture has no frame step (step 2) has no raw: leave its `tmp/` copy
   where it is, however exactly it matches, and name it in the report. Otherwise a raw belongs in the
   commit only when it is the capture its committed frame was made from, and a leftover from an
   uncommitted re-shoot is not — so test each one before moving it:
   - a frame `hairline.py` grew outward is the raw with a ring of the stroke width round it, so the
     frame cropped by that width on every side equals the raw pixel for pixel, except inside the
     corner squares `--radius` clipped when the frame is rounded;
   - a frame `hairline.py` traced inside a shaped raw has the raw's size and alpha, and differs only
     in a band the stroke width wide inside the silhouette;
   - a frame `winframe.py` drew has the raw's size, or the raw's plus twice the border thickness under
     `--grow`, and equals it wherever the content clip covers a pixel fully. Without `--grow` that
     clip is the frame inset by the border thickness t = floor((dpi + 48) / 96) px on every side, 2 px
     at 144 DPI, with its corners rounded; under `--grow`, offset the frame by t on each axis first,
     after which the clip is the raw's own extent less its corner arcs.

   Move each raw that passes to `docs/screenshots/raw/<frame file name>`. Leave one that fails where
   it is and name it in the report; nothing is lost either way, since `tmp/` is gitignored and was
   never the record. The other machine's `tmp/` may hold raws too: name that in the report rather
   than reaching for them, because a frame with no committed raw is re-framed by re-shooting it,
   which is how every frame was re-framed before this version.

Afterwards, `git status` should show the moved raws as new files under `docs/screenshots/raw/` and
the edits to `docs/_config.yml` and the capture code. Once pushed, confirm the Pages build succeeded
and that a raw's URL on the published site returns 404. Probe a raw this commit added, beside its
frame's URL, which must return 200. Where step 3 committed no raw, every URL under
`screenshots/raw/` returns 404 whether the exclusion works or not, so report the site check as not
covered and confirm the build only. A failed build keeps serving the previous deploy, which reads
exactly like an exclusion that worked.

## When it does not apply

There is no `docs/screenshots/capture/` directory. That is positive evidence that the repo takes no
screenshot by script, and a capture script is what writes a raw: without one there is no raw here
to commit and no capture code to point anywhere. Frames supplied by hand and framed later leave a
raw behind at that point, and the continuing rule reads the exclusion then.

## Continuing rule

`screenshot-raws-unpublished` — when `docs/screenshots/raw/` holds a file git does not hide and
`docs/_config.yml` exists, the config's top-level `exclude:` list carries `screenshots/raw/`,
`screenshots/raw/*` or `screenshots/raw/**`, optionally with a leading `/`. Two near misses do not
count: `./screenshots/raw/` excludes nothing, because Jekyll joins entries onto the source without
normalising them, and the bare `screenshots/raw` also drops every published frame whose name begins
`raw`, because Jekyll matches entries by prefix. A line inside that list the rule cannot read as an
item is reported rather than skipped, since it could be the entry the rule is looking for.
