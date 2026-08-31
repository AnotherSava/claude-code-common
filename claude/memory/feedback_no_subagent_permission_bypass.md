---
name: Never weaken permissions in a subagent prompt
description: Authorization for a task is not authorization to disable approval gates; never encode `--dangerously-skip-permissions` or any equivalent into a subagent's instructions
metadata:
  type: feedback
---

**Never instruct a subagent to run with `--dangerously-skip-permissions`, `--bypass-permissions`, or any equivalent.** Authorization for a *task* is not authorization to weaken the harness that supervises it.

Seen 2026-08-30: a recon prompt told a subagent to launch a throwaway Claude Code session with `--dangerously-skip-permissions`, in order to observe a message-hold path that only occurs when two sessions' permission modes differ. The safety classifier blocked the agent outright, and it was right to — the user had approved a four-stage build, and nothing in that approval touched permission checks on a research subagent.

**Why:** the reasoning that produces this is always *"it's a throwaway, in a temp dir, and it's the only way to observe X"* — which is exactly how a genuinely dangerous instruction gets written by someone acting in good faith. A scratch agent with approval gates off is still an autonomous agent with approval gates off, and its blast radius is the whole machine, not the temp dir. In that instance the observation was not even necessary: the same conclusion followed from the fact that the socket writes nothing back in *any* case, so the hold path could not have been observable regardless. The bypass would have bought nothing and cost the gate.

**How to apply:**
- If a behaviour seems to need weakened permissions to observe, treat that as a signal to find another route, or to report it unobserved and say which command would settle it. An honest UNVERIFIED beats a bypassed gate.
- If it genuinely requires it, ask the user in their own words first — never encode it in a subagent prompt, where it takes effect at exactly the moment they would otherwise have been asked.
- The same applies to anything else that widens a subagent's authority beyond your own: disabling sandboxing, granting blanket allowlists, or telling it to ignore a refusal. See [[feedback_surface_the_gap_dont_fill_it]] and [[peer_messaging]]'s permission-laundering rule — the same principle at other layers.
