---
name: feedback_verify_symptom_not_proxy
description: Confirm the symptom itself changed under the user's reported conditions, not a proxy signal or a convenient test scenario
metadata:
  type: feedback
---

Don't declare a user-visible symptom "fixed and verified" based on a proxy signal you *can* observe (a backend value, a binary timestamp, a log line) when you can't directly observe the symptom itself.

This session: the onboarding panel kept showing after restart. I diagnosed it as a stale binary (the deployed `.exe` predated the fix commit), redeployed, and said "Fixed and verified" — but I'd only confirmed `has_history: true` in the logs, not that the panel had actually disappeared (I couldn't see the GUI). It hadn't; the real cause was WebView2 serving stale cached frontend JS. The user came back with "I redeployed, and instructions are still there."

**Why:** an upstream value being correct does not prove the downstream symptom cleared — there can be another layer (here, a runtime cache) between the value and what the user sees.

**How to apply:** before claiming "fixed/verified" for something you can't directly observe, either get runtime evidence the *symptom itself* changed (instrument and read the actual behavior, not just the input to it), or scope the claim honestly: "the backend now reports X; can you confirm the panel is gone?" Don't let a plausible static diagnosis (timestamps, commit order) substitute for confirming the observable outcome. Relates to [[feedback_assumptions_vs_facts]].

**Second instance (same saga):** the next fix gated the cache-clear on the build fingerprint. I verified it — but only by relaunching *right after a deploy*, which always changes the fingerprint and always loads fresh. The reported condition was a Windows *restart* (same build, no deploy), where the fingerprint is unchanged and the bug recurs. Verifying a convenient proxy scenario (post-deploy relaunch) instead of the actual reported one (reboot/cold start) hid the failure. **Reproduce and verify against the user's real conditions, not a substitute that doesn't trigger the bug.**
