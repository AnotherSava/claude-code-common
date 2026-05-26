---
name: feedback-store-raw-derive-display
description: Store raw/rich data at persistence time; derive display-time fields rather than pre-computing or truncating
metadata:
  type: feedback
---

Store raw/rich data; derive display-time fields rather than pre-computing or truncating at storage time. If a field can be derived from stored data (even if the derivation is slightly more complex), store the source data and compute on demand.

**Why:** User corrected two design choices: (a) proposed truncating agent text to 2000 chars at storage → store full text, clean only for visualization; (b) proposed storing a pre-computed `is_task_prompt` boolean → store `status` (richer data) and derive `is_task_prompt` from the status sequence at display time.

**How to apply:** When designing persistence schemas, default to storing the raw signal (full text, original status, complete metadata). Add truncation, filtering, or derived booleans at the presentation layer where the display context determines what's needed.
