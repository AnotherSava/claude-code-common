---
created: 2026-09-13 04:41:44
platform: windows
---

# Share the three macOS-only capture guards with Windows, and require parity

The two documentation-capture halves have drifted. The `docs-relevance` skill states that the machinery lives in the skill and only the staging lives in the project — image processing was moved into `skills/docs-relevance/scripts/` and is genuinely shared, but the *policy* around the shutter was not, and now exists on one platform only.

## What has drifted

Measured 2026-09-13 in the tauri-dashboard repo's `docs/screenshots/capture/`:

- Windows: five `*-windows.ps1`, plus `lib/dashboard.ps1` and `lib/window-shot.ps1`
- macOS: five `*-macos.py`, plus `lib/dashboard.py`
- shared: `lib/trim_halo.py`, and this skill's `scripts/hairline.py`

Three things exist only on the macOS side. The absences come from grep over every `.ps1` and `lib/*.ps1`:

1. **`assert_publishable` / `names_in_frame` / `PUBLISHABLE_PROJECTS`** — the one that matters. It enforces a rule the user set: every session visible in any frame must be a publishable repo. On macOS the capture refuses, and it fired twice in the week to 2026-09-13, correctly both times — a peer session named `guild` was in frame. On Windows nothing checks, so the guarantee is whoever is driving remembering to look at the tab strip before the shutter.
2. **`keep_raw`** — archives the untouched capture to `tmp/raw/<stem>.raw.png`. Re-tuning post-processing (a border, a trim, a profile) then needs no re-capture, which on Windows means not taking over the user's machine, since that frame is read off the desktop with the always-on-top widget hidden.
3. **`config_value`** — a context manager that stages a config key and restores it, restoring an *absent* key by removing it rather than writing null. Writing null breaks `serde(default)` and silently reverts the whole config to defaults; that was a real bug, fixed on the macOS side only.

## The decision: a shared Python helper, not a port

A full port of the PowerShell to Python was proposed and argued down by the session that wrote `window-shot.ps1`. Its reasoning is the part worth keeping:

- Portable in principle — the 19 P/Invokes (`SetThreadDpiAwarenessContext`, `PrintWindow`, `DwmGetWindowAttribute`, `keybd_event`, `SetWindowPos`, `EnumWindows`) are ordinary ctypes calls with no exotic marshalling.
- The cost is the 27 `System.Drawing` references. `Add-Type` gives `Bitmap`/`Graphics`/`LockBits` free; `Graphics.FromImage().GetHdc()` is what hands `PrintWindow` a DC, and `LockBits` is what makes the pixel pass fast. Python gets no free ride: hand-roll `CreateCompatibleDC` + `CreateDIBSection` + `GetDIBits` through gdi32, then `Image.frombuffer` into Pillow — 80-120 lines of fiddly ctypes whose traps are stride, BGRA order, and top-down versus bottom-up origin, plus numpy as a new dependency.
- The decisive argument: the three gaps do not need 850 lines ported. They need a Python module both sides call, and the precedent already works — `window-shot.ps1` shells out to `trim_halo.py` today, using the same python/python3 PATH probe.
- Porting first would mean re-learning `PrintWindow` flag 3 (occluded windows), the XAML-islands blank-surface problem, and the two-exposure alpha keying in a second language *before* getting any of the benefit that motivated it.

So: shared helper now; the port only if it later earns itself.

## The work, in order

1. Write the parity requirement below into `skills/docs-relevance/SKILL.md` as a rule. Independent of the other three and far cheaper, so it can go first — and it is the only item that outlives this memo. Deliberately not done when this was captured: that file had uncommitted in-flight work on the same capture machinery, so the edit belongs with whoever finishes it.
2. `assert_publishable` into a Python module both sides call, invoked from PowerShell before the shutter. Highest value of the three, because it enforces a user-set rule currently enforced by eye on one platform.
3. `keep_raw`.
4. `config_value`.

Open, and better decided when the work starts than now: whether the shared module lands in this repo's `skills/docs-relevance/scripts/` (shared machinery, reaching every project) or in tauri-dashboard's `capture/lib/`. One reading is that the *mechanism* is skill machinery while the *list* is project data, so the function goes in the skill and takes the allowed set as an argument. That is a judgement, not a settled thing.

## The standing requirement

The user's own addition, and the reason this is a memo rather than only a fix: the two capture systems must stay **aligned in functionality**. A feature or safeguard added to one platform's capture path must also exist on the other, or be explicitly recorded as not applicable there, with the reason. This covers the extras and not just the core capture — raw archiving, the publishable guard, config staging, colour-profile handling, halo trimming, edge stroking, and whatever comes next. The failure mode is not that one side lacks a nicety; it is that a guarantee the user believes they have turns out to hold on one machine only, which is exactly what happened with the publishable guard.

**And aligned in *output*, not only in functionality.** Measured 2026-09-13, after the above was written. Asked to make the two platforms' frames the same shade of grey, they were not: every macOS frame was a flat `189` at full alpha, while the five Windows frames kept the OS's own *translucent* border and so took their shade from whatever sat behind the page — `159`–`183` on a white one, `53`–`54` on a dark one. GitHub renders a README in dark mode by default, so the divergence showed up precisely where most readers are. A feature can exist on both sides, be called the same way, and still produce two different pictures; a parity check that stops at "the code path exists" never sees it. State both halves in the rule.

The mechanics of that particular case — `--opaque`, and why stroking only the cut sides looks right on white and fails on dark — are already written into `skills/docs-relevance/SKILL.md`. So is the other finding from the same round: that `hairline.py` exited 0 whether it stroked a frame or decided the frame already had one, indistinguishable from success to its caller, fixed with a `--require` flag that asserts the *outcome* rather than that a stroke happened. Neither needs restating here. The rule written for item 1 states the principle and leaves the mechanics where they are.

The asymmetry that makes this easy to miss: the macOS half is where new work has been happening, so it accumulates features; the Windows half is edited rarely and from the other machine, so nobody notices it standing still. A parity check belongs wherever a capture feature gets added, which is why writing it into the skill is item 1 above rather than a closing suggestion — a memo gets checked off, and this requirement has to outlast that.

Phrase it there as a gate on *adding a capture feature*, not as a periodic audit: the point of failure is the moment one side gains something, and an audit only catches the drift much later, if anyone remembers to run it.

## Provenance

The absence claims are from grep over the committed files and are solid. Nothing about the PowerShell scripts' runtime behaviour was verified by running them — there is no pwsh on the Mac that measured this, and those scripts are twenty user32 P/Invokes deep regardless — so every runtime claim here is the Windows session's word, credited as such.
