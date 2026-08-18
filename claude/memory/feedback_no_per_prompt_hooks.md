---
name: No hooks that run on every prompt
description: Don't propose a hook firing on every user prompt — especially a blocking one; prefer a written guideline with an observable trigger or an on-demand check
type: feedback
---
Do not propose (or add) a hook that runs on **every** prompt, and least of all a blocking one that the turn has to wait on.

**Why:** a check that fires on all traffic to catch an occasional condition taxes every single turn with latency and noise, and the cost is paid most often exactly when the condition is absent. The user rejected a `UserPromptSubmit` hook that would have fetched from git on each message. (Established 2026-08-09.)

**How to apply:**
- Prefer a written guideline whose trigger I can actually observe, then act on it when it fires. Session transcripts carry per-message timestamps, so "has it been idle a while" is answerable without any hook.
- Reserve hooks for events that genuinely happen once (session start) or that must gate one specific tool call (a lint check on `PostToolUse` for edits).
- **Even a tool-scoped hook is too broad if it forks per call.** `matcher` scopes by tool *name* only; add the per-hook `if` field (permission-rule syntax, root-anchored — `Write(//**/SKILL.md)`) so non-matching calls never spawn the process. Measured on Windows: ~198ms of interpreter startup per non-matching `Write`/`Edit` with an in-script early-out, 0 with `if`. An early-out inside the script cannot recover that cost, because the process has already started. (Established 2026-08-17, after a hook on every Write/Edit was flagged as too much.)
- This narrows, not contradicts, the standing preference for enforcement at generation time over conventions — the enforcement still has to be proportionate to how often the condition occurs.
