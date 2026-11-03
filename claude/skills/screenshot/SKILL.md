---
name: screenshot
description: >-
  Take a picture of a window, a region or a menu on this machine — through DocShot on macOS, which holds the Screen Recording grant the terminal lacks, and through window-shot.ps1 on Windows — and owns the shared capture and framing scripts every project's capture code calls.
  TRIGGER when: any screen capture is about to be taken, debugging and measurement included; `screencapture` failed with "could not create image from display"; a capture came back blank or with every window title empty; or a script under this skill's scripts/ is being changed.
  DO NOT TRIGGER when: the picture is a documentation screenshot to be filed in a project's docs — that is `docs-screenshot`, which runs its own capture scripts and calls these tools directly — or the capture is a browser page the claude-in-chrome tools already screenshot.
---

# Screenshot

Takes the picture. What happens to it afterwards — framing for publication, filing, the manifest, the contact sheet — belongs to `docs-screenshot` in both cases: filing when the picture is going into a project's docs, and the contact sheet that reports it when it is a throwaway.

## Context
- Platform: !`uname -s`
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- DocShot installed (macOS): !`test -d ~/Applications/DocShot.app && echo PRESENT || echo MISSING`

Bare `scripts/` paths below are this skill's own, under `~/.claude/skills/screenshot/scripts/`.

## Process

1. **Write the capture into the repo's `tmp/`.** Use `<Repo root>/tmp/<what>-<date>.png`, never `$TEMP` or `/tmp`: the file tools refuse reads outside the working directories, so a capture written there cannot be opened to look at. The global excludes file ignores `/tmp/` at every repo root.

2. **Ask before a capture that takes the machine — once, before the first action of the burst.** A burst is everything from the first action that touches the user's screen through the shutter: launching or relaunching an app, raising a window, opening a menu, synthesizing a keystroke or click, moving the pointer, then the capture itself. This list is the one definition: `docs-screenshot`, `screenshot-relevance` and the README point here rather than restating it. Ask immediately before it starts, saying which app and windows it touches and roughly how long it takes, and run the whole burst on that one yes. Never ask again between staging and the shutter. A capture that touches nothing on screen needs no ask. Which captures take the machine:
   - **macOS:** DocShot launched with `open -g` on a window already on screen takes no focus and moves nothing, so it needs no ask on its own. Anything done to get the window there does.
   - **Windows:** `window-shot.ps1` always parks the pointer beside the window and puts it back when the capture ends, on every path, and restores a minimised window, and `-Method Screen` raises the window to the foreground, and `-Method Alpha` does too unless `-Popup` is given: a popup menu never becomes foreground, and raising it would let the ALT press dismiss the menu, so `-Popup` skips the raise. Every Windows capture takes the machine.

3. **Take the picture.**
   - **macOS — always through DocShot, never bare `screencapture`.** The terminal holds no Screen Recording grant, and its switch reading on in System Settings is not evidence that it does; DocShot is a small app bundle at a fixed path that holds the grant once. When **DocShot installed (macOS)** is `MISSING`, build it with `bash ~/.claude/skills/screenshot/scripts/build-docshot.sh`, then ask the user to grant DocShot Screen Recording in System Settings › Privacy & Security before the first capture. Never rebuild an installed one: rebuilding changes its ad-hoc signature and resets the grant, which is why the build script refuses without `--force`.
     Launch it through LaunchServices so the grant applies, and pass absolute paths, since `open` does not run it in the current directory:
     ```
     open -g -n -W -a ~/Applications/DocShot.app --args --owner <app> --out <abs path>.png
     ```
     Narrow with `--title <substring>`; take a window by `--id <n>`; take a rectangle with `--region x,y,w,h`; reach a menu or status item with `--layer <n>` or `--any-layer`; schedule a transient surface with `--delay <seconds>` and open it during the wait. To find what is on screen, `--list --out <abs path>.json` writes every window's id, owner, title, layer and bounds as JSON. Results always go to the `--out` file, because a process launched by `open` has no stdout of the caller's. Judge a run by that file, not by `open`'s exit status: a fast DocShot can exit before `open -W` looks for it, and `open` then fails with `Unable to block on application` although the file was written.
     **Probe the grant before trusting a blank result.** A denial is silent: window ids, owners and bounds still populate while every title comes back empty, so it reads as "nothing matches". `--check --out <abs path>.txt` writes `granted` or `denied`, and `--list` and `--check` exit 3 when it is denied. On `denied`, ask the user to re-grant DocShot; do not fall back to `screencapture`.
   - **Windows — through `window-shot.ps1`.** `pwsh -File ~/.claude/skills/screenshot/scripts/window-shot.ps1 -ProcessName <name> -TitleLike '<pattern>' -Method <m> -Out <path>.png`; `-List` lists the candidates. `PrintWindow`, the default, renders the window itself and works while it is covered; `Screen` reads the desktop after raising it and is the only one that keeps native chrome as the user sees it; `Alpha` shoots it over a black and a white backdrop and solves for real transparency, and is the one `-Popup` works with for a menu. A project's own `.ps1` capture script dot-sources `scripts/windows-capture.ps1` instead, which wraps this one.

4. **Read it back.** Open the PNG with the Read tool before drawing any conclusion from it. A capture of the wrong window, an empty one, or one with a tooltip across it fails silently otherwise.

## Scripts other projects call

Every project's capture code calls this skill's scripts by their path under `~/.claude/skills/screenshot/scripts/`, so renaming or moving one breaks a caller that will not notice until its next capture. The shutter is `docshot.swift` with `build-docshot.sh`, and `window-shot.ps1` with the `windows-capture.ps1` library over it; `check-capture-scripts.ps1` is what a project's commit gate runs, from the repo root, to resolve every library function its Windows captures use, so a renamed function fails that project's commit instead of its next capture, which would break after the pointer has moved. The framing tools — `hairline.py`, `outline.py` and `winframe.py` — live here beside the shutter, which calls `winframe.py` from `Add-WindowFrame`; when to use each is `docs-screenshot`'s.

Move or rename one of these only as a convention version under `claude/conventions/versions/`, which is how every caller's repo learns of the new path.

## Out of scope
- Do NOT capture on macOS with bare `screencapture`, or grant Screen Recording to the terminal or the agent binary
- Do NOT rebuild an installed DocShot without the user's go-ahead
- Do NOT file a capture into a project's docs from here — that is `docs-screenshot`. The one exception is the raw copy `Add-WindowFrame` makes into `docs/screenshots/raw/` on the Windows framing path, which the library does itself
- Do NOT copy a script from `scripts/` into a project; the project calls it by its path
