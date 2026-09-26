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

STATUS, re-measured 2026-09-26 against both trees. Items 2 and 3 are done and item 1 — the only one that outlives this memo — is not, which is the reverse of the order above.

- **Item 1 is still open.** Grep for `parity`, `both platforms` and `the other platform` across `skills/docs-relevance/` returns one hit, in an unrelated paragraph about contact-sheet links. Nothing in the skill gates adding a capture feature on the other platform having it.
- **Item 2 is done** — the same afternoon this was captured. `Assert-Publishable` in tauri-dashboard's `capture/lib/dashboard.ps1` (7a12eca, 2026-09-13) pipes `/api/agents` into `dashboard.py assert-publishable` and throws on a non-zero exit, so one rule is enforced from both libs. It is called from `compact-mode-windows.ps1`, `history-window-windows.ps1` and `terminal-tabs-windows.ps1`. Worth knowing before trusting it: no capture through any of those three has run since, so the guard has never actually fired on Windows.
- **Item 3 is done, and not where this memo expected.** Raw archiving went *skill*-side: `scripts/windows-capture.ps1` keeps each shot under `tmp/screenshot-raws` before post-processing, which is what let the tray-menu and work-intensity raws be re-framed on 2026-09-25 without re-capture.
- **Item 4 is still open, and the divergence it names is now visible in the tree.** `compact-mode-windows.ps1` carries its own inline `Set-CompactMode`, a duplicate of the macOS `config_value`, and it reads the prior state as `$was = [bool]((...).compact_mode)` — so a config that never held the key restores as `compact_mode: false`, writing a setting the user never set. That is a milder failure than the `null` one this memo records (a `false` parses, where a `null` reverted every field to its default), but it is the same class and the same absent-key case. The fixture path is not a substitute: `Invoke-DashboardFixture` does stage config through the shared Python, but wholesale via `fixture-up`/`fixture-down`, which is a different operation from staging one key.

The open question below is answered, by what the two finished items did rather than by a decision: they went opposite ways, and both correctly. The publishable guard stayed project-side, in tauri-dashboard's `capture/lib/dashboard.py`, with PowerShell shelling out to it — because the allowed *list* is project data. Raw archiving went into the skill, because keeping a shot before post-processing is machinery every project wants. So the split the paragraph guessed at holds, applied per item.

Open, and better decided when the work starts than now: whether the shared module lands in this repo's `skills/docs-relevance/scripts/` (shared machinery, reaching every project) or in tauri-dashboard's `capture/lib/`. One reading is that the *mechanism* is skill machinery while the *list* is project data, so the function goes in the skill and takes the allowed set as an argument. That is a judgement, not a settled thing.

## The standing requirement

The user's own addition, and the reason this is a memo rather than only a fix: the two capture systems must stay **aligned in functionality**. A feature or safeguard added to one platform's capture path must also exist on the other, or be explicitly recorded as not applicable there, with the reason. This covers the extras and not just the core capture — raw archiving, the publishable guard, config staging, colour-profile handling, halo trimming, edge stroking, and whatever comes next. The failure mode is not that one side lacks a nicety; it is that a guarantee the user believes they have turns out to hold on one machine only, which is exactly what happened with the publishable guard.

**And aligned in *output*, not only in functionality.** Measured 2026-09-13, after the above was written. Asked to make the two platforms' frames the same shade of grey, they were not: every macOS frame was a flat `189` at full alpha, while the five Windows frames kept the OS's own *translucent* border and so took their shade from whatever sat behind the page — `159`–`183` on a white one, `53`–`54` on a dark one. GitHub renders a README in dark mode by default, so the divergence showed up precisely where most readers are. A feature can exist on both sides, be called the same way, and still produce two different pictures; a parity check that stops at "the code path exists" never sees it. State both halves in the rule.

The mechanics of that particular case — `--opaque`, and why stroking only the cut sides looks right on white and fails on dark — are already written into `skills/docs-relevance/SKILL.md`. So is the other finding from the same round: that `hairline.py` exited 0 whether it stroked a frame or decided the frame already had one, indistinguishable from success to its caller, fixed with a `--require` flag that asserts the *outcome* rather than that a stroke happened. Neither needs restating here. The rule written for item 1 states the principle and leaves the mechanics where they are.

The asymmetry that makes this easy to miss: the macOS half is where new work has been happening, so it accumulates features; the Windows half is edited rarely and from the other machine, so nobody notices it standing still. A parity check belongs wherever a capture feature gets added, which is why writing it into the skill is item 1 above rather than a closing suggestion — a memo gets checked off, and this requirement has to outlast that.

Phrase it there as a gate on *adding a capture feature*, not as a periodic audit: the point of failure is the moment one side gains something, and an audit only catches the drift much later, if anyone remembers to run it.

## Provenance

The absence claims are from grep over the committed files and are solid. Nothing about the PowerShell scripts' runtime behaviour was verified by running them — there is no pwsh on the Mac that measured this, and those scripts are twenty user32 P/Invokes deep regardless — so every runtime claim here is the Windows session's word, credited as such.
