---
name: feedback_verify_gui_via_repro
description: When you can't observe a bug directly, find a signal that proves the mechanism before proposing a fix — never deploy-and-ask on unverified reasoning
metadata:
  type: feedback
---

When a bug can't be verified from the harness — a desktop WinForms/WPF window with no screenshot tool, a video player the automation tab won't autoplay — don't deploy a fix that's reasoned-but-unchecked and ask the user to eyeball it. Find something observable first: a tiny throwaway repro that *logs the numbers*, or an artifact that already exists (a server log, a request pattern, a counter). Reproduce the failure in that signal, then confirm the fix flips it. Delete any repro afterward.

**Why (1):** In achievement-overlay's Add-game dialog, a clipped two-line status label got a confident first fix (double `PerformLayout`) that was deployed and *failed* — the user had to re-test and report "same". A ~5-minute console repro then showed the real cause immediately (`content.Height` came out 6px under `grid.Height`; the height formula hand-summed the chrome with a `+8` constant that under-counted the button-bar row's margin) and proved the corrected formula — `grid.Height + (ClientSize.Height - content.Height)`, i.e. measure the realized non-content chrome instead of approximating it — made it fit (`FITS=True`).

**Why (2), 2026-08-11, what-is-next:** an in-app video player never resumed where it left off. Three fixes were reasoned from the code, deployed, and handed over to test — "still same" each time. What actually found it was reading the dev-server log, which had been sitting there the whole while: 7 teardown calls against 1 progress call proved the reports were being dropped *inside the component*, and later, counting HLS fragments per play session proved the viewer had been scrubbing rather than watching, which demolished the theory the last two fixes rested on.

**How to apply:** When you can't see the result, find the signal *before* proposing a fix — an existing log, a counter, a request pattern, a small measuring repro. It lets you iterate solo without a user round-trip per attempt. Never say "try it now" about a fix whose mechanism you haven't observed; state what you verified and what you didn't. Three consecutive "still same" replies is the signal to stop patching and go instrument. Reserve deploy-and-ask for when getting a signal genuinely costs more than the round-trip. Relates to [[feedback_verify_before_justifying]] and [[feedback_no_guessed_facts]].
