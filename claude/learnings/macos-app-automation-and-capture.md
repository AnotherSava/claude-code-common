# Driving and photographing a local macOS app from an agent

Two jobs that look like one — *make the app show something*, and *capture what it
shows* — with different permissions, different failure modes, and a strong right
answer for each.

## Staging: climb down from the top, never start at the bottom

| rung | mechanism | permission |
|---|---|---|
| 1 | the app's own interface — URL scheme, CLI, local HTTP route | **none** |
| 2 | App Intents / `shortcuts` | per-shortcut, user-visible |
| 3 | Apple Events against the app's `.sdef` | Automation, **scoped per source→target pair** |
| 4 | Accessibility API — find the element, `AXPress` it | Accessibility (system-wide) |
| 5 | synthesized clicks at coordinates (`CGEventPost`) | Accessibility (system-wide) |

Rung 5 needs the *same broad grant* as rung 4 while being strictly more fragile —
it breaks the moment a row moves. It is never the right first choice, and a
helper that injects input is a general "control this machine" capability that a
permission classifier will refuse, correctly.

**For an app you own, the answer is to give it rung 1 rather than to puppet its
UI.** A named action on a loopback route needs no OS permission, says what it
means, and survives a redesign. Check first — `Info.plist` for
`CFBundleURLTypes` / `NSAppleScriptEnabled`, and `Contents/Resources/*.sdef` —
before assuming rungs 1–3 are unavailable.

The line worth holding: a control surface commands *what is shown*; it must not
fabricate *what is true*. "Open the chart at week N" and "show session X" are
target selectors and belong there. Seed data, a demo mode, or a fixture added to
make a picture look better does not.

## Capture: where the Screen Recording grant goes matters

Not to the agent's own binary. A native Claude Code install is a bare executable
named after its version (`~/.local/share/claude/versions/2.1.251`), so:

- the TCC prompt shows **"2.1.251"** — the filename, because an unbundled binary
  has no `Info.plist` and no display name;
- the grant goes stale on every update, since the next version is a different
  path;
- it hands whole-display access to *every* agent session, permanently, for one
  screenshot.

Use a small purpose-built `.app` at a fixed path with an ad-hoc signature
(`codesign -s -`). Granted once, narrow, and survives updates. **Rebuilding it
changes the signature and resets the grant** — build once, and keep any
no-permission post-processing in a *separate* plain binary so improving that
never costs the grant.

### Three traps, each of which reads as something else

**TCC attributes to the responsible process, not the executed binary.** Running
`Helper.app/Contents/MacOS/helper` directly from a shell is attributed to the
calling agent, so the helper's own grant is ignored and it fails exactly as if
ungranted. It must be launched through LaunchServices:

```
open -n -a ~/Applications/Helper.app --args --out /tmp/result.json
```

Which forces the second half: a LaunchServices-started process does **not**
inherit the caller's stdout. Every mode needs a `--out <file>`, including the
ones that only print — otherwise the answer goes nowhere.

**A Screen Recording denial is silent and looks like an empty screen.**
`CGWindowListCopyWindowInfo` still returns ids, owners and bounds; only `title`
comes back empty. Probe for it explicitly rather than discovering it as a black
PNG.

**The obvious probe false-passes.** "Some window reports a title" is true without
any grant: `Window Server`'s layer-24 `Menubar` is readable ungated, as is any
window the calling process owns. Only a *foreign, ordinary* window's title is
gated:

```swift
rows.contains { $0.layer == 0 && $0.owner != "Window Server" && !$0.title.isEmpty }
```

## Not everything worth capturing is a window

Menus, popovers, tooltips and status items are separate `CGWindow`s on higher
layers — a menu is ~101, a menu-bar item ~25 — so a `layer == 0` filter silently
discards them, and a size floor discards status items. Three things follow:

- make the layer filter a *default*, not a rule;
- support a plain `--region x,y,w,h` for what has no window of its own;
- apply any delay **before** enumerating, since a transient surface has to be
  opened after the capture is already scheduled.

Refuse an ambiguous match rather than picking one. Window titles collide in
practice — a terminal mirrors its session name, so photographing a dashboard's
"foo" window can silently catch the terminal's "foo" instead.

## Transparency and borders are post-processing, not capture

A dark screenshot on a dark page has no visible boundary. macOS gives a
*decorated* window a light ~`(189,189,189)` hairline and transparent rounded
corners for free; an **undecorated** window has neither, and a region crop never
does. Both are just alpha and a stroke — read the PNG, clip to a rounded path so
the corners become transparent, stroke the same grey, write it back. No
permission needed, so it belongs in a plain binary.

Sample before assuming: `(0,0,0,0)` corners with a light top-edge pixel mean the
window already brought its own, and stroking a square border over it will cut
across the rounded corners.
