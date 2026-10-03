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

## The task-notification `.output` file is an envelope, not the return value
On completion the notification's `<output-file>` holds `{"summary", "agentCount", "logs", "result"}` — the script's return value sits under `.result`, not at the top level. The notification itself truncates a long result, so reading that file is the normal way to see all of it, and parsing it as though it were the bare return value fails with `JSONDecodeError: Extra data`. Read it as `json.loads(p.read_text(encoding="utf-8"))["result"]`.

## A saved workflow added mid-session is not found by name until the next session
`Workflow({name})` resolves against built-ins, the user scope `~/.claude/workflows/*.js` and each project's `.claude/workflows/`. The installed binary reads the user scope from the config directory's `workflows/` and lists it with source `userSettings`. A file there must start with a pure-literal `export const meta` naming it, and one with an unparseable meta is skipped with only a debug-log warning. The list of all workflows sits in a session cache (`allWorkflows`, keyed partly on the working directory), so once it is filled a workflow file or directory created later fails with `Workflow "<name>" not found. Available: <built-ins only>`, although the file is valid and in the right place. Measured 2026-10-02: a `~/.claude/workflows` link created mid-session, in a session that had already run a workflow, was missing from the name lookup; what fills the cache was not pinned down beyond that. A session started later finds it by name, and a name is the only route that works from any repo. `Workflow({scriptPath, args})` runs the file at once only where the session can already read it — its working directory or an added directory: from this repo the `~/.claude/workflows/<name>.js` path resolves into the checkout and runs, while a session in another repo is refused with "scriptPath must be a script path this tool returned, or a file you can already read". There, copy the script into that repo's gitignored `tmp/` and run the copy.

The Workflow tool also refuses a script containing a carriage return ("control characters that would be hidden in the approval dialog"), so a CRLF working copy fails even when the committed blob is LF. Measured 2026-10-02 on Windows, a workflow's fixer subagent left three files it edited as CRLF, by a route not pinned down. One confirmed route: Python's `open(path, "w")` in text mode translates every `\n` to `\r\n` on Windows, so a script edited by a `python` one-off that reads and rewrites it comes back CRLF — write with `newline=""` or in binary. `git ls-files --eol <path>` shows `w/crlf` against `i/lf`, and rewriting the file with LF fixes it.
