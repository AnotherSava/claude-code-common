# Events, matchers, payloads, and return values

Verified against the official hooks reference on 2026-08-19. Where the docs are thin, the fallback
that has worked is grepping `claude.exe` for the field name to find its schema — do that rather
than guessing what a payload contains or what order events fire in.

## Events and cadence

| Event | Cadence | Can block? |
|---|---|---|
| `SessionStart`, `SessionEnd` | once per session | no |
| `UserPromptSubmit`, `Stop`, `StopFailure` | once per turn | `UserPromptSubmit` only |
| `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`, `PermissionDenied` | per tool call | `PreToolUse` only |
| `FileChanged`, `CwdChanged`, `WorktreeCreate`, `WorktreeRemove`, `Notification`, `ConfigChange`, `InstructionsLoaded`, `DirectoryAdded` | async, off the main loop | no |
| `MessageDisplay` | **per streaming chunk** | rewrites the delta |

The `EndConversation` tool skips `PreToolUse` and `PostToolUse`.

All hooks matching one event run **in parallel**; there is no ordering between them. The same
handler registered in multiple settings files runs once, but plugin and skill copies run
separately.

## Matcher targets

| Event | Matcher matches against | Example |
|---|---|---|
| `PreToolUse` / `PostToolUse` | tool name | `Bash`, `mcp__memory__.*` |
| `Notification` | `notification_type` | `permission_prompt`, `idle_prompt`, `plan_approval` |
| `SessionStart` | start mode | `startup`, `resume`, `clear` |
| `SubagentStart` | agent type | `general-purpose`, `Explore` |
| `StopFailure` | error type | `rate_limit`, `authentication_failed` |

Exact string match unless the value contains regex metacharacters, in which case it is an
unanchored `test()`. Characters that keep it an exact match: letters, digits, `_`, `-`, space,
`,`, `|`. Omitting the matcher, or `"*"`, matches everything.

`notification_type` values seen in practice: `permission_prompt`, `idle_prompt`, `plan_approval`,
plus other attention signals. **`idle_prompt` fires after an idle timeout of roughly 60 s** — it
means the human has not typed, not that the model finished.

## The `if` field

Gates on tool *arguments* and is evaluated before any process spawns:

```json
{ "matcher": "^Write$", "hooks": [ { "type": "command", "if": "Write(//**/SKILL.md)", "command": "…" } ] }
```

**Put `if` inside the hook object**, as above. This example previously showed it as a sibling of `matcher`;
whether that form also works is untested, and the live `settings.json` — the only instance known to fire — uses
the placement shown here. Prefer the proven one.

The `//` root anchor is mandatory. Without it the rule matches nothing and the hook silently never
runs — it fails closed and quietly, so verify it fires before assuming it works.

**The value is a permission rule**, the same syntax `permissions.allow`/`deny` take, so the tool name is part
of it: `Edit(*.ts)` and `Bash(git *)` are both valid, and a bare string with no `Tool(…)` wrapper is not.
Evaluated only on `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest` and
`PermissionDenied`; on any other event a hook carrying an `if` never runs at all.

A `Bash(…)` pattern matches the *command and its arguments*, per the upstream table (2026-09-18):

| `if` pattern | command | runs? | why |
|---|---|---|---|
| `Bash(git *)` | `FOO=bar git push` | yes | leading assignments are stripped first |
| `Bash(git *)` | `npm test && git push` | yes | every subcommand is checked separately |
| `Bash(rm *)` | `echo $(rm -rf /)` | yes | `$()` and backticks are checked too |
| `Bash(cat *)` | `echo before $(date) after` | no | neither the whole command nor `date` matches |
| `Bash(git *)` | `$TOOL git push` | yes | an unresolvable command name runs the hook anyway |
| `Bash(git push *)` | `echo $(date)` | yes | a pattern naming more than the command runs on any `$()`, backtick or `$VAR` |

The last two rows are the shape to plan around: **`if` is best-effort and fails open**, so anything it cannot
parse spawns the hook. Upstream says as much — use `permissions.deny` when the requirement is a hard block
rather than a cheap gate. What this means for a *nested* interpreter is that the pattern sees the outer
command only: a `New-Item` inside `powershell -Command "…"` is matched as `powershell *`, never as `New-Item *`.

## Async and timeouts

- `"async": true` — background, does not block, cannot influence the turn or a permission
  decision. stdout/stderr are shown only with `asyncRewake`.
- `"asyncRewake": true` — background, but wakes Claude on exit 2. Implies `async`.
- Default is `false`, i.e. blocking.

| Hook type | Default timeout |
|---|---|
| `command`, `http`, `mcp_tool` | 600 s — **but 30 s under `UserPromptSubmit`, 10 s under `MessageDisplay`** |
| `prompt` | 30 s |
| `agent` | 60 s |

`SessionEnd` shares a 1.5 s budget across all its hooks, raised toward 60 s only if an individual
hook sets a larger `timeout`.

On timeout the hook is cancelled, output discarded, no decision rendered. A timed-out `PreToolUse`
does **not** block — the call proceeds.

`StopFailure` accepts `command` hooks only, not `http` / `prompt` / `agent`.

## Exit codes

| Code | Effect |
|---|---|
| 0 | success. stdout parsed as JSON if the first non-whitespace char is `{`, else treated as plain text. **stderr goes to the debug log only — Claude never sees it.** |
| 2 | blocks, regardless of any JSON. stderr becomes the reason. `PreToolUse` blocks the call; `UserPromptSubmit` rejects the prompt; `PostToolUse` shows stderr to Claude (the tool already ran); non-blocking events show stderr to the user only. |
| other | non-blocking error and the action proceeds — unless stdout carries schema-valid JSON, which is then honoured as if 0. |

## JSON output

Available on every event:

```json
{ "continue": false, "stopReason": "...", "systemMessage": "...", "terminalSequence": "" }
```

Tool events additionally:

```json
{ "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny|allow|escalate",
    "permissionDecisionReason": "...",
    "additionalContext": "...",
    "updatedInput": { "command": "modified" } } }
```

`PermissionDenied` supports `retry: true`; `FileChanged` and `InstructionsLoaded` support
`skipNotification: true`. Strings are capped at 10,000 chars — oversized output is written to a
file and previewed.

Pair `additionalContext` with `suppressOutput: true` when the user does not need to see the
reminder. Note that `additionalContext` lands in the transcript, so anything a hook injects
repeatedly accumulates there.

The mutation-capable set is `MessageDisplay`, `PreToolUse.updatedInput`,
`PostToolUse.updatedToolOutput`, and `PermissionRequest.updatedInput` — nothing else can change
what actually happens or what the user sees.

## Stdin payload

```json
{
  "session_id": "…", "prompt_id": "…",
  "transcript_path": "…/transcript.jsonl",
  "cwd": "…", "permission_mode": "default|plan|acceptEdits|auto|dontAsk|bypassPermissions",
  "hook_event_name": "PreToolUse",
  "effort": { "level": "high" },
  "tool_name": "Bash", "tool_input": { … }, "tool_use_id": "toolu_…",
  "agent_id": "…", "agent_type": "…"
}
```

- `cwd` is the *live* working directory, which may not be the project root — prefer
  `CLAUDE_PROJECT_DIR`.
- On `SessionStart` the transcript file may not exist yet; treat `ENOENT` as benign.
- `prompt` appears only on `UserPromptSubmit`; use it verbatim if persisting it.
- `notification_type` appears only on `Notification`; `source` only on `SessionStart`; `reason`
  only on `SessionEnd`.

## Environment

`$CLAUDE_PROJECT_DIR`, `$CLAUDE_PLUGIN_ROOT`, `$CLAUDE_PLUGIN_DATA`, `$CLAUDE_EFFORT`,
`$CLAUDE_CODE_REMOTE`, `$CLAUDE_CODE_BRIDGE_SESSION_ID`. The parent shell environment is
inherited; all `OTEL_*` exporter variables are stripped.

Hook processes are spawned with `CREATE_NO_WINDOW` on Windows — a fresh invisible console, no
controlling TTY, and stdout captured with ESC bytes stripped.

## What hooks cannot see

There is no hook for a mid-turn user interrupt (ESC), for thinking, or for a terminal resize.
`Stop` fires *before* the final assistant text is flushed to the transcript — roughly a 350 ms
race — so a hook that reads the transcript on `Stop` may miss the last message. Use a file watcher
as the authority when that matters.
