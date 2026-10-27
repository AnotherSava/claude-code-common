---
name: feedback_label_example_output
description: Output shown to illustrate a change comes from the user's real data or is labelled as an example; a fixture's sentence shown bare reads as a finding
metadata:
  type: feedback
---

When a reply shows output to illustrate a change — a warning sentence, a label, a message the app now
produces — take it from the user's real data, or say plainly that it is an example. A sentence produced by a
test fixture, shown bare beside real results, reads as a statement about their data.

Real case 2026-10-23: a new double-booking warning was illustrated with the expected string of a unit test,
naming a hotel on the user's current trip as booked twice for one night. The trip had real bookings at that
hotel, and they asked "is it?" — the two stays did not overlap at all.

**Why:** the user reads the shown output as what the product says about them, and a fixture's dates and names
are often borrowed from their real data, which makes it more convincing and more wrong.
**How to apply:** prefer an instance the real data produces; where none exists, write "for example" or "a test
case produces", and never place a fixture's output in the same list as measured results.
