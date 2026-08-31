---
name: feedback_rotate_dont_abandon
description: When a credential leaks, propose rotating it rather than abandoning the capability — a leak makes one value worthless, not the access
metadata:
  type: feedback
---

When a credential is exposed, frame the response as **replacing the value**, not as giving up the access. Say what is being rotated, what survives the rotation, and what capability is preserved.

**Why:** on 2026-08-30 a Backblaze master key leaked into a session transcript, and it was reported to the user as something to destroy — "the leaked key needs to be rotated" stated as pure loss. The user had to ask *"don't you want to keep it to manage backups for other services when they ask?"* before it was framed correctly. The capability had been deliberately acquired minutes earlier, for exactly that reason, and the leak did not change any of the reasoning that justified holding it. Presenting a rotation as an abandonment silently discards a decision the user just made, and invites re-litigating it under time pressure.

The framing also buries the useful fact, which is usually that rotation is **cheap**. Here, regenerating the master key invalidated only the previous master secret and left every scoped application key working — so the fix was one console click plus one re-store, not a rebuild of anything.

**How to apply:**
- Lead with the replacement, not the loss: "regenerate it and hand me the new one" rather than "this must be revoked".
- State explicitly what does *not* break — which dependent credentials, jobs or integrations survive.
- **Verify the old value is actually dead** rather than assuming the rotation killed it; a rotation that silently left the old secret valid is the case that matters, and it costs one API call to rule out. See [[feedback_no_guessed_facts]].
- Reserve "stop holding this at all" for when the *capability* was the mistake — not when only its current value was exposed.
- Spend the compromised credential first when it is still valid and there is provisioning work it would otherwise block, then rotate immediately after. That shortens its live window rather than adding a round trip.
