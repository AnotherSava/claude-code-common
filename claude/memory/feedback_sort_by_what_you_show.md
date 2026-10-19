---
name: feedback_sort_by_what_you_show
description: when a view starts displaying an override value, route its ordering and next/current logic through the same value
metadata:
  type: feedback
---

When a view starts displaying an override (a stated value beside a stored one), route its ordering and its
"next/current" logic through the same value. A list sorted by a value it does not draw reads as broken.

Real case 2026-10-19: a stay showed the stated 22:00 arrival but was sorted by its 15:00 check-in window, so
it sat ahead of the train that arrived at 21:56. The user reported it as a bug within minutes of using the
feature.

**Why:** the user reads order from the values on screen; a hidden sort key contradicts them.
**How to apply:** when adding the override, grep every comparator and "which one is next" check over the
stored field, and decide for each whether it serves display (use the override) or accounting (keep stored).
