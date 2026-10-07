---
name: feedback_base_rate_before_a_detector
description: Before building a detector, alert or gate for a condition, measure how often the condition already holds — one that is the resting state makes a signal nobody reads, so condition on the narrower predicate that tracks the harm
metadata:
  type: feedback
---

**Before building a detector, an alert or a gate, measure how often its condition already holds.**
A condition that is the resting state produces a signal that is wallpaper and a gate that is a work
stoppage, and both get overridden or ignored inside a week.

**Why:** Asked to surface a desktop app's installed build falling behind its repo, the obvious
design was a check for "install != HEAD". Measured 2026-10-06 from cargo's fingerprint directories:
the install lagged the tree in 32 of 38 recoverable compile events, median 22.9h, so the condition
held most of the time while exactly one case in ~182 code commits did any harm. The harm tracked
something much narrower — the commit added a serialized field to a published API that an
out-of-process reader consumes — which was 17 of those 182 commits and included the one that caused
the incident. The narrow notice shipped; the detector did not.

This is the frequency of the *condition*, not of the problem, which is why
[[feedback_realism_before_hardening]] does not catch it: a condition can be permanent while its harm
is rare, and rating the edge case's realism says nothing about how often the check would fire. An
always-firing signal is the "icon stuck on interacting" failure in a new place — it teaches the user
to ignore the one time it matters.

**How to apply:** Ask what fraction of the time the condition is true before designing anything, and
measure it rather than estimating — the history is usually recoverable from build artifacts, a log,
or git. If it is common, do not detect it; find the predicate that separates the harmful instances,
and pin that predicate to a known instance so it cannot drift away from the case it exists for.
State the measurement's instrument and direction of error, since these counts are usually bounds
rather than figures. See also [[feedback_measure_the_composite]].
