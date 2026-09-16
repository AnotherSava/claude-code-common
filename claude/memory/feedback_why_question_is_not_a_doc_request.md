---
name: feedback_why_question_is_not_a_doc_request
description: a question asking why a design is the way it is is not a request to document the rationale; answer in chat and wait
metadata:
  type: feedback
---

A question asking *why* a design is the way it is is not a request to write the rationale down. Answer it in chat and stop there.

**Why:** On 2026-09-16, asked "why not just a single version = highest version it has adopted", I gave four reasons and in the same turn added a "Why a record and not a high-water mark" section to the doc. The next message was "don't rush making changes, let's discuss this", followed by an argument that dismantled the first reason; the whole section was deleted hours later when the design changed. A written rationale reads as settled and is harder to abandon than a paragraph in chat, so the edit cost nothing to make and something to undo.

**How to apply:** Distinguish the two shapes. "What does X mean here?" is a comprehension question — answer it and fix the doc that was unclear, which is the right move. "Why is it X and not Y?" is often the opening of a disagreement; answer it and wait for the next message before committing the answer to a file. Write it down once the design has survived the conversation, not during it. Related: [[feedback_discuss_before_rewriting_design]].
