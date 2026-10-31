---
name: feedback_no_null_result_lines
description: Leave a step out of a report when it had nothing to do; a line saying so is noise
metadata:
  type: feedback
---

A report line saying a step had nothing to do is noise: "no workflows, so nothing to watch", "no other repos to hand
off", "neither wrapper is configured", "no v* tag". Leave such steps out of the report entirely.

**Why:** on 2026-10-30 the user listed four such lines from one push report and asked for them gone; three were already
forbidden by the skills that produced them.

**How to apply:** before sending a report, delete every line whose content is that something did not apply. A step whose
result is unknown — CI exists but cannot be watched — is not a null result and stays.
