---
name: feedback_transient_control_sticky_for_mount
description: A control shown because a count is non-zero must not vanish when the count drops — hide it on arrival, keep it for the life of the mount
metadata:
  type: feedback
---

A nav entry, badge or section that appears only when a count is non-zero must not disappear the moment
that count drops to zero. Hide it on **arrival**; keep it for the life of the **mount**.

**Why:** the trips nav grew an `Inbox N` entry rendered only when the review queue held something.
Accepting the last item took the count to zero, which deleted the control the reader was standing on,
mid-row, reflowing the two beside it. The user's words on 2026-09-21:

> if it disappears in the middle of the section it might look weird, though i agree that you shouldn't
> show empty inbox in the new session or even after reload

Both halves matter and they pull opposite ways. A stale zero is noise when you arrive — a permanent
"Inbox 0" claims a third of the nav to say nothing, on almost every day. A disappearance is noise
mid-interaction, and worse, because it moves the thing under the pointer.

**How to apply:**

- Make the visibility **sticky per mount**, not per render: `useState(false)`, set during render when the
  count first goes above zero, and read as `count > 0 || everOccupied`. A reload starts clean, which is
  exactly where "do not show an empty one" was wanted.
- **Not an effect.** An effect paints one frame without the control and then adds it — the same flicker
  this exists to prevent, arriving from the other end. Render-phase `setState` from props is the
  documented React pattern for derived state and is what belongs here.
- The rule is about the control's *existence*. Whether a zero renders greyed-out or absent is a separate
  question, and the answer differs per control: a permanent place whose emptiness is itself an answer
  ("Upcoming 0" is news) greys out; a queue that is empty most days goes away.

Distinct from [[feedback_empty_state_names_the_filter]], which governs what an empty *view* says once you
are in it. This one governs whether the control that got you there is still on screen.
