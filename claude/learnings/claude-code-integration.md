# Integrating with Claude Code

Reference for projects that report Claude Code session state, tail its transcripts, or otherwise observe session lifecycle. Covers the three integration surfaces, hook payload schema, transcript JSONL layout, and common gotchas.

## Three integration surfaces

1. **Hooks** (primary) — lifecycle events run in the Claude Code harness. Deterministic, fire-and-forget, no impact on Claude's context window.
2. **MCP tools** (secondary) — for mid-response state that Claude can voluntarily report (e.g. `thinking`, `error`). Spawned per session as stdio children.
3. **Transcript tailing** (tertiary) — for filling gaps between hook events: long tool loops, resumption after permission prompt, intermediate reasoning.

A hook-primary design beats an MCP-primary one for routine cases: hooks don't require Claude to remember to call a tool, don't cost turn context, and fire deterministically.

## Hook events

Configure in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "<EventName>": [
      { "hooks": [ { "type": "command", "async": true,
          "command": "python3 /path/to/script.py <arg>" } ] }
    ]
  }
}
```

Always pass `async: true` so the hook POST doesn't block Claude's turn.

| Event | When it fires | Naive status mapping |
|---|---|---|
| `SessionStart` | Session begins — source field distinguishes `startup` / `resume` / `clear` / `compact` | `idle` |
| `UserPromptSubmit` | User submits a prompt | `working` |
| `Notification` | Claude requests permission, fires an idle prompt, or sends a desktop notification | `awaiting` |
| `Stop` | Claude finishes the current response (one turn, not one task) | `done` — but see "Done vs awaiting" below |
| `SessionEnd` | Session exits (`/exit` or window close) | `clear` (remove row) |
| `PostToolUse` (matcher: `ExitPlanMode`) | User approved a plan | trigger plan-archival side effects |

Also worth knowing about but usually not needed for state reporting: `PreToolUse`, `SubagentStop`.

## Hook stdin payload

Each hook receives a JSON payload on stdin. Common fields:

- `session_id` — UUID string, stable for the lifetime of one Claude Code session (preserved across `/clear` and `/compact`).
- `transcript_path` — absolute path to the session's JSONL transcript.
- `cwd` — the Claude Code process's working directory (the project root when launched in a project).
- `prompt` — present only on `UserPromptSubmit`.
- `message` — present on `Notification` (the notification text).
- `notification_type` — present on `Notification`: `permission_prompt`, `idle_prompt`, `plan_approval`, or other attention signals. **Critical for state classification** (see next section).
- `source` — present on `SessionStart`: one of `startup`, `resume`, `clear`, `compact`.
- `reason` — present on `SessionEnd`.
- `tool_input`, `tool_response` — present on `PreToolUse` / `PostToolUse` hooks.

**Race to be aware of:** on `SessionStart` the transcript file may not exist yet — Claude Code creates it lazily when the first conversational entry is written. Treat `ENOENT` on `transcript_path` as a benign log-only event. The next hook call (`UserPromptSubmit`) will arrive after the file exists.

## Classifying session state: done vs awaiting vs idle

The single most common integration mistake is treating `Stop` as "Claude completed the request." It doesn't — `Stop` fires at the end of **every assistant turn**, which includes:

1. Claude finished the whole task.
2. Claude asked the user a clarifying question and is waiting for an answer.
3. Claude reported partial progress ("done with step 3 of 5, continuing...") before the next turn begins automatically via tool results.

Case 3 is rare because `Stop` only fires when the current turn has no pending tool calls — if Claude is mid-tool-chain, the model keeps going and `Stop` is suppressed. But cases 1 and 2 are indistinguishable from the `Stop` payload alone. `stop_reason` in the transcript is `end_turn` for both.

### Three distinct "not working" states

A useful state enum separates:

- **`idle`** — session is present, nothing is happening. Baseline after `SessionStart`, or after a long quiet period with no active request. The user isn't blocked, Claude isn't blocked.
- **`done`** — Claude finished a piece of work and there's no pending user action. Use for "task complete, report delivered."
- **`awaiting`** — Claude is specifically blocked on user input. Asked a question, needs tool approval, waiting for plan approval. The user is the one who needs to act.

The naive single-`idle`-bucket approach conflates "session is dormant" with "user is blocking the session," which hides the signal you most want to see ("something needs me").

### The `?`-heuristic

Since the hook payload doesn't carry a "done vs awaiting" flag, read the last assistant text block from the transcript and classify on whether it ends with `?`:

```python
def last_assistant_ends_with_question(transcript_path: str) -> bool:
    last_text = ""
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            msg = json.loads(line).get("message", {})
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                last_text = content.strip()
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text" and block.get("text", "").strip():
                        last_text = block["text"].strip()
    return last_text.endswith("?")
```

Reference implementation: `D:/projects/claude/claude/hooks/notifications/telegram.py:83-101`.

Accuracy is ~80–90% in practice. Known misses:
- "Anything else?" at the end of a true completion → false `awaiting`.
- "Here's the answer." at the end of a response that implicitly asks for direction → false `done`.

Both misses are symmetric and non-catastrophic — the dashboard row briefly shows the wrong state until the next turn corrects it. For higher stakes (archiving a plan file, sending a notification) either accept the ~10% failure rate or add an explicit marker from Claude.

### Recommended classification by hook

| Hook (arg to script) | Payload signal | Emitted state | Label (if any) |
|---|---|---|---|
| `SessionStart` | — | `idle` | (preserve) |
| `UserPromptSubmit` | `prompt` | `working` | first line of prompt, 60-char cap |
| `Stop` | last assistant ends with `?` | `awaiting` | "has a question" |
| `Stop` | last assistant does not end with `?` | `done` | (preserve) |
| `Notification` | `notification_type == "permission_prompt"` | `awaiting` | `"needs approval: <tool>"` (parse tool name from message) |
| `Notification` | `notification_type == "plan_approval"` | `awaiting` | "plan approval" |
| `Notification` | `notification_type == "idle_prompt"` + `?` | `awaiting` | "has a question" |
| `Notification` | `notification_type == "idle_prompt"` + no `?` | `done` | (preserve) |
| `Notification` | any other `notification_type` | `awaiting` | `message` |
| `SessionEnd` | — | `clear` | — |

### Notification debouncing

`idle_prompt` fires after Claude Code's internal idle timeout (typically ~60s). If you want to suppress transient idle states (user alt-tabbed, came back seconds later), sleep for a grace period and check whether the session transcript mtime changed in the meantime — if it did, the user re-engaged and you skip the notification. Reference: `telegram.py:36-57` uses a 60s `NOTIFICATION_DELAY` and compares `~/.claude/projects/<mangled>/*.jsonl` mtime against `time.time() - NOTIFICATION_DELAY`.

This matters for loud channels (Telegram, SMS, desktop push). For silent UI state updates (a dashboard row color change) the debounce is optional.

## Transcript JSONL location and filename mangling

Path: `~/.claude/projects/<mangled-cwd>/<session-id>.jsonl`.

CWD mangling replaces `:` and `/` (and `\`) with `-`, leaves existing `-` alone. The mangling is **lossy** — `D:/projects/foo-bar` and `D:/projects/foo/bar` both mangle to `D--projects-foo-bar`. Reverse lookup from mangled path back to cwd is unreliable. **Always use the `transcript_path` passed by the hook, never reconstruct it from cwd.**

## Transcript entry types

Each line is a JSON object with a top-level `type`. Entries that carry conversation content:

- `type: "user"`, `message.role: "user"` — a user message (text block) or a tool result coming back to Claude (tool_result block).
- `type: "assistant"`, `message.role: "assistant"` — Claude's output; may contain `text` and/or `tool_use` blocks.

Metadata entries that should be skipped when inferring state:
- `attachment`
- `file-history-snapshot`
- `system`
- `permission-mode`
- `last-prompt`
- `queue-operation`

## Sidechain and synthetic assistant entries

Not every `type: "assistant"` entry represents the main session's model. Two flavors are dangerous because they look real at a glance but will clobber any "find the most recent assistant and read its model/usage" lookup:

- **`isSidechain: true`** — sub-agent invocations (Task / Explore / custom agents). Sidechains run with their own system prompt, tool set, and often a different model. Their `message.usage` reflects the sub-agent's context window, not the parent session's. If you're reporting "how full is this session's context?", picking up a sidechain's numbers will be wrong and whiplash as sub-agents spin up and finish.
- **`message.model: "<synthetic>"`** (usually paired with top-level `isApiErrorMessage: true`) — placeholder entries that Claude Code inserts for API errors, rate-limit notices, and similar system events. They carry a `usage` block but all counts are zero. They have `isSidechain: false`, so the sidechain filter alone misses them.

Both bit the dashboard in April 2026: the per-row context color flashed red after every first response because the newest assistant entry in the freshly-appended transcript chunk was either a sub-agent or a `<synthetic>` error, with a model string that didn't match the configured `claude-opus-4-7 → 1M` window mapping.

Fix pattern — require both checks when extracting model or usage:

```js
if (type === "assistant" && !obj.isSidechain) {
  if (typeof msg.model === "string" && msg.model.startsWith("claude-")) {
    // real main-session entry — safe to read msg.model and msg.usage
  }
}
```

The `startsWith("claude-")` guard is the cheapest robust discriminator against `<synthetic>` and any future non-model placeholder strings. Don't trust `isApiErrorMessage` alone — it's not set on every synthetic entry and new placeholder shapes may not carry it.

State inference (the `working`/`done` decision) can still use sidechain and synthetic entries — they represent real activity within the session from the user's perspective. Only the model/usage extraction needs the filter.

## Inferring state from the last conversational entry

Walk entries backwards; use the last one whose type is `user` or `assistant` and whose `message.content` is a valid array:

| Last conversational entry | Inferred state |
|---|---|
| `assistant` with a `tool_use` block | `working` (Claude called a tool, waiting for result) |
| `user` with a `tool_result` block | `working` (result arrived, Claude will process it) |
| `user` with a `text` block | `working` (user sent a message, Claude is about to respond) |
| `assistant` with only `text` (no pending tool) | `done` (turn complete) |

Empty text blocks (whitespace-only) don't count as `text`.

## Chat ID derivation from cwd

Readable names beat session UUIDs for UI. Common scheme:

1. If cwd is under a configured `projects_root` (e.g. `D:/projects`), use the relative path with `/`, `-`, `_` translated to spaces: `D:/projects/bga/assistant` → `bga assistant`.
2. Otherwise, use the cwd basename unchanged.
3. Fallback when cwd is absent: `claude-<session_id[:8]>`.

Note that rule 1 changes `-` → space but rule 2 does not. A folder literally named `watcher-error` under `projects_root` becomes chat_id `watcher error`; outside `projects_root` it stays `watcher-error`.

## MCP server conventions

For projects that also register an MCP server:

- **Lifetime**: spawned per Claude Code session; one process lives for the whole session.
- **Chat ID locking**: lock the first `chat_id` passed to `set_status` and reuse it for the rest of the process — don't let Claude accidentally spawn multiple dashboard entries.
- **Error surfacing**: the MCP `tool` response must not surface errors about downstream failures (a missing widget, network blip, etc.) — that creates noise in Claude's reasoning. Log to a disk file instead. Return success on any fire-and-forget outcome.
- **Session ID from env**: Claude Code may expose `session_id` to the MCP server via env var; check `process.env` before falling back to the locked-chat-id approach.

## Renderer-facing gotchas

- Hooks load at session start; existing sessions don't pick up `settings.json` changes until `/exit` + relaunch.
- `fs.watch` on transcript files can fire multiple times per write on Windows; debounce with a `pending` flag and a `dirty` re-entry flag.
- Position tracking when tailing: the file can be truncated in rare edge cases; reset position to 0 if current `stat.size` is less than the last known position.
- Partial JSON lines: read up to the last `\n` in the chunk, keep the leftover for the next read. Never `JSON.parse` a partial line — skip and retry on the next event.

## Plan-mode lifecycle hooks

Plan mode writes its approved plan to `~/.claude/plans/<auto-slug>.md`. Two hook events bracket the implementation phase:

- **Plan approval**: `PostToolUse` hook with `matcher: "ExitPlanMode"`. Fires once when the user accepts the plan. The `tool_response` payload contains `plan` (the markdown). This is the right place to move/copy the plan to a project-tracked location.
- **Plan completion**: there is no direct hook for "implementation finished." Options in decreasing order of reliability:
  1. **Manual slash command** — user-triggered, always right.
  2. **On next `ExitPlanMode`** — archive the previously active plan when a new one is approved.
  3. **Notification + `?`-heuristic** — on `idle_prompt` without a trailing `?`, treat as "truly done" and archive. Has the same ~10% miss rate as the state classifier.
  4. **`SessionEnd`** — archive whatever's active when the session closes. Conflates "done" with "abandoned."

The `PostToolUse`/`ExitPlanMode` matcher is narrow enough that the hook doesn't need additional filtering:

```json
"PostToolUse": [
  { "matcher": "ExitPlanMode",
    "hooks": [ { "type": "command", "async": true,
        "command": "python3 /path/to/archive-plan.py start" } ] }
]
```

## Hook diagnostic technique

Claude Code doesn't surface hook script errors to the user by default (especially with `async: true`). If a hook isn't firing as expected, log to a disk file from the script itself — not stdout — and inspect after a test prompt. Bash/Python scripts can write a single JSON-line log.

## Reference implementations

- **Dashboard with transcript tailing + state classifier**: `D:/projects/claude-status-dashboard/integrations/claude_hook.py` (hook arg dispatcher, chat_id derivation, `?`-heuristic), `src/log-watcher.cjs` (JSONL tail + `inferState` + token usage extraction).
- **Telegram idle notifier with debouncing**: `D:/projects/claude/claude/hooks/notifications/telegram.py` (notification_type classifier, `?`-heuristic, mtime-based activity debounce, last-prompt recall).
- **Prompt recorder**: `D:/projects/claude/claude/hooks/notifications/record-prompt.py` (writes last user prompt to a per-project temp file so later hooks can recall it).
