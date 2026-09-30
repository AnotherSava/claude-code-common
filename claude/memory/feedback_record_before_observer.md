---
name: feedback_record_before_observer
description: asked to distinguish two states, check whether the system already witnessed the thing that separates them before designing something that goes and looks
metadata:
  type: feedback
---

When asked to distinguish two states, first ask whether the system already *witnessed* the event that separates them. Building an observer for a fact that arrives as an event is expensive, and it is usually less certain than the event.

**Why:** 2026-09-30, asked to tell an agent with nothing left to do from one with unfinished work. I designed an observer: resolve each row's working directory, poll git there on some cadence, cache it, put it on a thread, degrade for rows with no path and for peers whose tree is on another machine — plus an admission that half the definition was not observable at all and I would have to either guess it or leave it out. The user's whole reply was: *"i think you overcomplicate things: agent goes into clean state after performing /clear and after completing peer request to pull changes if it was in clean state before this request."* Every one of those is an event the system already receives. What shipped reads two fields that were already arriving on every session start and being thrown away.

**How to apply:** when the user's own definition is phrased as **"after X happens"**, that is a record and not a measurement — go and find where X already arrives before designing anything that goes and looks. Two further tells that a record beats an observer: the observed thing can change while nobody is watching, so any poll is stale by its own interval; and the observer usually cannot answer for a remote machine at all, where a recorded event travels perfectly well.

Not an argument against measurement in general — it is an argument for checking the inbox first. Adjacent to [[feedback_complexity_may_be_self_imposed]], which asks whether a constraint is real; this one asks whether the work is necessary at all.
