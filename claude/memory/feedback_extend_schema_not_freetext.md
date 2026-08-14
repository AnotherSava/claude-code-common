---
name: feedback_extend_schema_not_freetext
description: When data doesn't fit an existing format, offer extending the schema as the recommended option instead of defaulting to a free-text workaround
metadata:
  type: feedback
---

When a piece of information doesn't fit an existing data format, extend the format rather than
stuffing it into a free-text field. Offered a date range that the travel-map visit schema couldn't
express — a new optional `end` field versus putting "Until 7 October" in the existing `comment` —
the user chose the schema change (2026-08-11), even though it meant touching render code and docs
rather than only data.

**Why:** free text loses the structure. Nothing can sort, filter, or render on a fact buried in a
comment, and the same gap recurs on every later entry of the same shape.

**How to apply:** when data doesn't fit, present the schema extension as the recommended option and
price it honestly (name the files that change) instead of quietly picking the cheaper workaround.
Still ask rather than deciding alone — the extension touches code, and it is the user's call. Watch
for the tell that makes it worth raising: the shape is not a one-off, so a comment hack would be the
first of many. See [[feedback_no_premature_abstraction]] for the other side — this is about data
that genuinely exists now, not a field added speculatively.
