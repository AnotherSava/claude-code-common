# Verifying macOS window behavior via Accessibility (System Events)

How to prove a macOS window-geometry or menu change actually took effect at
runtime, without guessing from source review alone.

## Drive geometry through AXSize, not visual inspection

To prove a resize lock, min/max constraint, or anchor behaves as coded, set
the window's `AXSize` via System Events and read it back:

```
osascript -e 'tell application "System Events" to tell process "<app-name>" to set size of window 1 to {W, H}'
osascript -e 'tell application "System Events" to tell process "<app-name>" to get size of window 1'
```

Setting `AXSize` goes through `setFrame:`, which AppKit constrains the same
way a user edge-drag is — so an A/B (feature on vs off, same request, same
window position) is decisive proof, not an inference. This needs
Accessibility permission granted to whatever is running the `osascript` (once
granted, no further prompts).

## Three traps that cost real time

- **A sleeping or locked display makes the window look destroyed.** System
  Events reports `Can't get window 1 … Invalid index (-1719)` / `count of
  windows = 0`, and `screencapture` writes an all-black PNG. The app itself is
  fine (check its own logs if it has any) — this is purely a display-state
  artifact. `caffeinate -u` does **not** reliably wake a sleeping display, and
  does nothing for a *locked* one. Check for a black screenshot before
  suspecting the code under test.

  To positively confirm the screen is **locked** (as opposed to some other
  capture failure worth actually debugging):

  ```
  ioreg -n Root -d1 -a | plutil -convert json -o - - | python3 -c \
    "import json,sys; print(json.load(sys.stdin)['IOConsoleUsers'][0]['CGSSessionScreenIsLocked'])"
  ```

  When the screen is genuinely locked, don't try to unlock it — that's the
  user's session. Report the limitation instead of guessing at the render
  from code review alone.

- **Screen-edge clamping masquerades as the constraint under test.** AppKit's
  `constrainFrameRect:toScreen:` truncates any frame request at the work-area
  edge, so a "blocked" resize can just be the window hitting the screen
  boundary rather than the app's own lock. Move the window somewhere with
  room first, or the A/B test proves nothing.

- **A successful click can leave state behind.** `click menu item …` returns
  an object reference on success — that reads like noise in the output and is
  easy to misjudge as a failure, especially when a sleeping/locked-display AX
  error lands in the same breath. Exploratory clicks on menu items that toggle
  persistent UI state (a panel visibility flag, a mode that only resets on
  relaunch) can leave the app in a different state than before the test.
  Undo any UI state a verification pass sets, and confirm the undo — don't
  assume a clean exit.
