---
name: verify-log-timing
description: Before designing transcript/log-tailing detection, empirically verify the writer's flush behavior
metadata:
  type: feedback
---

Before designing detection logic that tails a log file written by another process, empirically verify when entries actually land on disk. Compare file mtime against external evidence of the event timing — don't assume "the writer flushes immediately."

**Why:** I implemented "detect unresolved AskUserQuestion tool_use in the JSONL transcript" for the dashboard, deployed it, and the bug persisted. I concluded that Claude Code buffered the tool_use until its tool_result was ready, on one observation of the file staying silent for 5+ minutes during a prompt plus 9-min and 38-min gaps between tool_use and tool_result timestamps — gaps that an immediate write produces just as well, since each entry is stamped when created. ~30 minutes of work lost. On 2026-09-28 a measurement across 160 `AskUserQuestion` calls on 2.1.235–2.1.283 found the tool_use line written while the prompt was still on screen (`learnings/claude-code-integration.md`, "User-gating tools in the transcript"); whether the earlier version buffered was never re-checked. So the one conclusion drawn without the check below stood as fact for months, which is the case for running it.

**How to apply:** When the proposed detector says "look for unresolved/pending X in this file," do a one-shot empirical check first:
1. Trigger the live state in question.
2. `stat` the file — does mtime advance?
3. `tail` the file — are the bytes you expect actually there?
If the file is silent during the state, the data isn't on disk; transcript-side detection cannot work. Switch to event-driven (hook/IPC) or a different signal.

Related: [[feedback_verify_before_justifying]] — verify before defending; same root principle, applied to legacy code.
