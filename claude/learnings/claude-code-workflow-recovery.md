# Workflow tool: hangs, resume, and recovery

Hard-won gotchas from running long fan-out `Workflow` scripts (the `Workflow` tool that orchestrates subagents). These are about the harness, not any one project.

## An agent can hang mid-task and stall the whole run
A subagent occasionally fetches its answer but freezes **before emitting its structured result** — no `result` event is ever written. Inside a `parallel()` (or `pipeline()` with a barrier), that one hung agent stalls the whole call indefinitely; the workflow never returns. Symptom: the run sits at N-1/N for many minutes. (Observed repeatedly on the *same* input across separate runs — some inputs reliably trigger it, so it's worth suspecting a specific item, not just bad luck.)

Detect it: the run's `journal.jsonl` shows one `started` with no matching `result`, and that agent's `agent-<id>.jsonl` file hasn't been written to in a long time (`stat`/mtime).

## Recovery, in order
1. `TaskStop` the workflow (it won't finish on its own).
2. **Resume** with `Workflow({scriptPath, resumeFromRunId})` — completed agents replay from cache, only the hung one re-runs. **You MUST re-pass the same `args`** on resume; omitting `args` crashes the script immediately (`args` is `undefined` → e.g. `convs.length` throws) with **zero** agents run. Resuming without args is the #1 self-inflicted failure.
3. If it hangs again, **harvest** instead of re-running. Read the run's `journal.jsonl` under
   `~/.claude/projects/<mangled-project-id>/subagents/workflows/<runId>/`. Each `type:"result"` entry holds the agent's returned object — **but only the schema fields**, not the post-`.then()` mapping, so results are unlabeled. Map each result back to its input by reading that agent's `agent-<id>.jsonl` transcript and pulling the prompt (e.g. the line that names the item). The missing item = the hung agent; grab its answer straight from its transcript if it got that far.

## Web-search budget is session-wide and shared with workflow agents
`WebSearch` has a per-**session** cap (default 200) shared across the main loop **and every workflow subagent**. A big research fan-out can exhaust it; afterwards, subsequent agents silently can't search and fall back to `WebFetch` only (their transcripts show "Web search budget … 200 of 200"). Consequence: a second research workflow later in the same session may return degraded "not found" results not because the data is absent but because the agents couldn't search. Budget searches across the whole session, or lead with `WebFetch` of known authoritative URLs (often better than search anyway for facts like pricing/dates on an official page).

## Journal is the source of truth for what an agent returned
Before concluding a workflow "returned nothing," read `journal.jsonl` — cached/returned values are recorded there. Don't assume a cached result was non-empty.
