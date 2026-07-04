---
name: feedback_verify_gui_via_repro
description: For desktop-UI sizing/layout bugs you can't screenshot from the harness, build an isolated measuring repro to verify before deploying
metadata:
  type: feedback
---

When a UI bug can't be visually verified from the harness (a desktop WinForms/WPF window — no screenshot tool for the OS desktop), don't deploy a fix that's reasoned-but-unchecked and ask the user to eyeball it. First build a tiny throwaway repro that replicates the exact layout/structure and *logs the numbers* (measured heights, sizes, offsets), reproduce the bug there, then confirm the fix flips the failing measurement. Delete the repro afterward.

**Why:** In achievement-overlay's Add-game dialog, a clipped two-line status label got a confident first fix (double `PerformLayout`) that was deployed and *failed* — the user had to re-test and report "same". A ~5-minute console repro then showed the real cause immediately (`content.Height` came out 6px under `grid.Height`; the height formula hand-summed the chrome with a `+8` constant that under-counted the button-bar row's margin) and proved the corrected formula — `grid.Height + (ClientSize.Height - content.Height)`, i.e. measure the realized non-content chrome instead of approximating it — made it fit (`FITS=True`).

**How to apply:** For desktop-UI sizing/layout bugs, reach for an isolated measuring repro early rather than deploy-and-ask. A repro that prints the relevant metrics lets you iterate solo without a user round-trip per attempt. Reserve deploy-and-ask for when the repro genuinely costs more than the round-trip. Relates to [[feedback_verify_before_justifying]].
