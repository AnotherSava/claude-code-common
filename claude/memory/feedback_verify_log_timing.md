---
name: verify-log-timing
description: Before designing transcript/log-tailing detection, empirically verify the writer's flush behavior
metadata:
  type: feedback
---

Before designing detection logic that tails a log file written by another process, empirically verify when entries actually land on disk. Compare file mtime against external evidence of the event timing — don't assume "the writer flushes immediately."

**Why:** I implemented "detect unresolved AskUserQuestion tool_use in the JSONL transcript" for the dashboard, deployed it, and the bug persisted. The writer (Claude Code) buffers the assistant message containing certain client-side tool_use blocks and flushes only once the matching tool_result is ready. The transcript file was silent for 5+ minutes while the user was being prompted. Older transcripts confirmed 9-min and 38-min gaps between tool_use and tool_result timestamps. The "unresolved-X" probe could never fire by construction. ~30 minutes of work lost.

**How to apply:** When the proposed detector says "look for unresolved/pending X in this file," do a one-shot empirical check first:
1. Trigger the live state in question.
2. `stat` the file — does mtime advance?
3. `tail` the file — are the bytes you expect actually there?
If the file is silent during the state, the data isn't on disk; transcript-side detection cannot work. Switch to event-driven (hook/IPC) or a different signal.

Related: [[feedback_verify_before_justifying]] — verify before defending; same root principle, applied to legacy code.
