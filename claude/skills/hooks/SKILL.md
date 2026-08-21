---
name: hooks
description: >-
  Author, register, and optimize Claude Code hooks — choosing the event and matcher, keeping the
  per-invocation cost down, and the never-raise contract every hook script owes the harness.
  TRIGGER when: writing or editing a hook script, adding or changing a `hooks` entry in
  `settings.json`, diagnosing a hook that never fires or fires too often, or deciding whether
  something should be a hook at all.
  DO NOT TRIGGER when: the subject is git hooks (pre-commit, pre-push), React hooks, or Win32
  hooks — unrelated senses of the word.
---

# Claude Code hook authoring

Every hook is a process spawn on somebody's critical path. This skill exists so that cost is
chosen deliberately rather than discovered later.

Read `references/performance.md` before picking an interpreter or an event — it carries the
measured cost table. Read `references/events-and-payloads.md` for the event catalog, matcher
semantics, exit codes, and the stdin payload shape.

## 1. First decide it should be a hook

A hook is the right tool when the behaviour must happen *without anyone remembering to ask for
it*, and the trigger is an event the harness already emits. It is the wrong tool when a guideline
or an on-demand check would do.

- **Never register a hook that runs on every prompt**, and least of all a blocking one — see
  `~/.claude/memory/feedback_no_per_prompt_hooks.md`. The cost is paid most often in exactly the
  case where the hook does nothing.
- Enforcement at generation time (a `PostToolUse` lint hook) beats a convention that relies on
  remembering — but only once it is narrowed per §2.
- If the work is "do X when the user asks", that is a skill or a slash command, not a hook.

## 2. Narrow before you spawn — the ladder

Apply the cheapest gate that expresses the condition. Each rung avoids the entire cost of the one
below it.

1. **`if` field** — pattern-gates on tool *arguments* and costs **zero process startup** when it
   does not match. `"if": "Write(//**/SKILL.md)"`. The `//` root anchor is required; without it
   the rule silently matches nothing and the hook never runs.
2. **`matcher`** — gates on the event's discriminator (tool name for `PreToolUse`/`PostToolUse`,
   `notification_type` for `Notification`, start mode for `SessionStart`). Exact string unless it
   contains regex metacharacters. An absent matcher means *every* occurrence of that event.
3. **In-script early return** — the last resort. It runs *after* the interpreter has started, so
   it saves the body's work but never the startup cost. Order these cheapest-first (§4).

A matcher-less `PreToolUse` or `PostToolUse` forks on every single tool call. That is the most
expensive mistake available here.

## 3. Choose `async` deliberately

Default `async: true`. A synchronous hook is on the user's critical path, so reserve it for the
cases that must return a decision or context to the model:

- a permission decision (`hookSpecificOutput.permissionDecision`)
- `additionalContext` the model needs this turn
- exit code 2 to block the action

Everything else — telemetry, state files, notifications, archiving — is fire-and-forget.
`asyncRewake: true` is the middle ground: background execution that wakes Claude on exit 2.

## 4. Order checks cheapest-first

Inside the script, put the discriminator that rejects most invocations at the top, and anything
involving IO at the bottom. Concretely, in ascending cost: a payload field comparison → an
`os.environ` lookup → a `Path.exists()` → a directory glob → reading a file → parsing the session
transcript → forking `git` → a network call.

Reading `transcript_path` means streaming the whole session JSONL to EOF. Never do it before the
cheap checks that would have returned.

## 5. The never-raise contract

A hook must not be able to disrupt Claude Code. Every script in this repo follows this and new
ones must too:

- Wrap the stdin parse in a bare `try/except` that falls back to `{}` and exits 0.
- Give every subprocess, file operation, and network call its own swallow.
- Exit 0 on every path except a deliberate block (exit 2).
- Pass `timeout=` to every `subprocess` call and every HTTP request.

**Errors are not surfaced**, especially with `async: true` — a broken hook fails silently. If a
hook does anything consequential, append a JSON line per decision to a log under `~/.claude/`,
through a helper that itself cannot raise. `plan-archive.py` is the reference implementation, and
its log is what made a misfire diagnosable after the fact.

## 6. Script hygiene

- **Windows UTF-8** — Claude Code sends UTF-8 bytes; Python on Windows decodes stdin with the
  system codepage and mangles non-ASCII before your logic runs. `sys.stdin.reconfigure(encoding="utf-8", errors="replace")`
  at the entry point, guarded by `hasattr`. Same for stdout when the hook prints.
- **Derive cwd** as `CLAUDE_PROJECT_DIR` → `payload["cwd"]` → `os.getcwd()`. Add
  `git rev-parse --show-toplevel` only when the target is repo-relative.
- **`realpath` before git** when the path may be a symlink out of the worktree — everything under
  `~/.claude/` is symlinked from the dotfiles repo.
- **Unknown `argv[1]` must be a no-op**, so a stale command string in `settings.json` cannot
  re-arm a removed mode.
- The **shebang is dead text** when the hook is invoked as `python script.py`; it only applies if
  the script is executed by path, which is also the slowest form.

## 7. Registering it

`~/.claude/settings.json` is a symlink into the dotfiles repo — Write and Edit refuse to write
through symlinks, so resolve it with `readlink` and edit the real path.

The file stores escaped quotes as literal `"`, which defeats exact-string editing. Edit it
programmatically, then `json.loads` the result **before** writing it back — a syntax error here
breaks every hook at once.

**Hooks load at session start.** An existing session keeps the old configuration; relaunch to pick
up a change. This is the usual reason a just-added hook "doesn't work".

## 8. Verify

1. `python -m py_compile <script>` — it must at least parse.
2. Feed it each payload shape on stdin directly and assert the exit code and stdout. Redirect
   `HOME`/`USERPROFILE` to a temp dir for any run that writes, so real logs and state stay clean.
3. Test the *discard* path as well as the acting path — that is the path that runs most.
4. Time it: `time (for i in $(seq 20); do ... ; done)` and divide. Compare against
   `references/performance.md`; a hook meaningfully above the floor is doing work it could defer.
5. After any `settings.json` edit, confirm the JSON parses **and that every command string still
   runs**. Parsing is not sufficient — `python -S` fused to the quoted path with no separating
   space is valid JSON and dies with `Unknown option: -/`. Build the edit in a temp copy, execute
   each command, and only then copy it over the live file: settings hot-reloads on write, so the
   first bad save is already in force.
6. Clean up temp dirs and confirm nothing reached the real log.

## 9. Findings log

This section accumulates. When a hook surprises you — a cost, a silent failure, a semantic — add a
dated line here rather than leaving it in a session transcript.

- **2026-08-19** — `python3` on this machine is a 29-byte bash shim that execs `python`, costing
  **+23 ms on every invocation** for no behaviour change. All 18 hook commands were switched to
  `python`; measured after the change, `plan-archive.py done` went 96 → 72 ms and the statusline
  hook 108 → 84 ms. The statusline runs every 2 s, so that one alone returns ~0.7 s of CPU per
  minute. Write `python` in new hook commands. Note the shim is also a shell *alias*, which is why
  it looks free interactively — aliases don't expand in the non-interactive shell that spawns hooks.
- **2026-08-19** — Nothing is free: the Windows process-spawn floor is ~29 ms, and a Python hook
  that does nothing but parse stdin and discard costs ~61 ms. Budget per *invocation*, not per
  line of script.
- **2026-08-19** — Bash is not the lightweight option. One fork (`cat`, `grep`) costs 62–64 ms —
  worse than Python doing a real JSON parse. Bash only wins with builtins and zero forks (~33 ms).
- **2026-08-19** — Trimming imports is a non-fix: the whole typical set costs 2.8 ms, while
  `site.py` alone costs 18.4 ms. Script length is not the lever either (0.2 KB → 11.4 KB spans 6 ms).
- **2026-08-19** — `Notification` fires on an idle *timeout* (~60 s of no user input), not a turn
  boundary. It is not a "the model finished" signal, and nothing about it implies work completed.
- **2026-08-19** — `MessageDisplay` forks **per streaming chunk** with a ~10 s timeout that blocks
  TUI rendering. Treat it as the most expensive event in the system.
- **2026-08-19** — Hooks run under `CREATE_NO_WINDOW` with a fresh invisible console and no
  controlling TTY; Claude captures stdout and strips ESC bytes.
- **2026-08-19** — A content-matching gate fires on prose, not just on commands. `doppler-guard.py`
  triggered while writing *documentation that mentions* `doppler-guard.py`. Harmless here, but it
  is why content matching is the last rung of the ladder: it cannot distinguish doing the thing
  from writing about it, and every false positive is a synchronous interpreter start.
- **2026-08-19** — A hook whose trigger carries no information about the condition it is testing
  will misfire, however good its checks are. `plan-archive.py done` inferred "the plan is
  finished" from an idle timeout and archived a plan four minutes after it was written. Ask what
  the event actually proves before hanging an action on it.
- **2026-08-21** — A malformed command in a blocking `PreToolUse` hook matched on
  `^(Bash|Write|Edit)$` disables all three mutation tools at once, leaving no way to repair
  `settings.json` from inside the session — the user has to run a shell command. The JSON-parses
  check does not catch it, because the file stays well-formed. Validate a candidate copy by
  running its commands before overwriting the live file (§8.5).

## Out of scope

- Do NOT add a hook without narrowing it per §2 first.
- Do NOT register a hook on every prompt, or a blocking hook on a hot event.
- Do NOT edit `settings.json` through the symlink, or without validating the JSON afterwards.
- Do NOT restate content that `references/` or a cited memory already owns — add a pointer.
