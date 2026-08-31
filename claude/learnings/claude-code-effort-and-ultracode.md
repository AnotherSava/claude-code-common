# Reasoning effort and ultracode in Claude Code

How hard Claude thinks per turn is one setting with five ways to set it and two different value sets,
and the docs surface almost none of it. Everything below was read out of the shipped binary (see the
last section) against Claude Code 2.1.251.

## The two value sets are not the same, and that is the trap

| Where | Accepted values |
| --- | --- |
| Live session — `/effort`, `--effort`, `CLAUDE_CODE_EFFORT_LEVEL` | `low` `medium` `high` `xhigh` `max` |
| Persisted — the `effortLevel` settings key | `low` `medium` `high` `xhigh` |

`max` exists only as a session level. Putting `"effortLevel": "max"` in a settings file is not a valid
value for that key, so a config that looks like it pins the top level does not. Pin `xhigh` and reach
`max` per session, or use `ultracode` (below), which forces `xhigh` rather than `max`.

## Precedence, strongest first

1. **`CLAUDE_CODE_EFFORT_LEVEL=<level>`** — an env var override. While it is set, `/effort` refuses to
   change the level and tells you to clear it first.
2. **`claude --effort <level>`** — that invocation only.
3. **`/effort <level>`** — live, mid-session. Its own help: *"`/effort` controls how long Claude thinks
   before answering. `high` for tricky bugs, `low` when you just need a quick edit."*
4. **`"ultracode": true`** in settings — forces `xhigh` outright.
5. **`"effortLevel"`** in settings — the standing default.
6. **`"modelSettings": { "<canonical-model-name>": { "effortLevel": ... } }`** — per-model, same
   4-value enum. Note `ultracode: true` returns `{default, byModel: {}}`, so it **discards** every
   per-model override rather than layering over them.

The effort resolver reads the *merged* settings across all sources (user → project → local → flag →
policy), so the key works in `~/.claude/settings.json` like any other.

## `ultracode` is a settings key, despite what its description says

```json
{ "effortLevel": "xhigh", "ultracode": true }
```

Its schema description reads *"Enable ultracode for the session: xhigh effort plus standing
dynamic-workflow orchestration. Session-scoped — typically provided via `--settings` or the
`apply_flag_settings` control request; interactive toggles never persist it. Requires workflows to be
enabled and an xhigh-capable model."*

"Session-scoped" describes what it *means*, not where it may be written — and "interactive toggles
never persist it" is the point worth reading twice: toggling ultracode in the UI never writes the key
back, so the only way to make it standing is to put it in a settings file by hand. It is then read on
every session start.

What it actually turns on is two things, and the second is the expensive one: xhigh effort, **plus** a
standing instruction to author and run a multi-agent workflow for every substantive task, with token
cost explicitly not a constraint. That is a large multiplier on ordinary turns, not only big ones.

Prerequisites, both of which fail silently if unmet: workflows enabled (`enableWorkflows`, not
`disableWorkflows`) and a model that supports `xhigh`. On a model with no reasoning-effort parameter
the CLI reports `Effort not supported` and sends none.

## Related keys worth knowing

- **`workflowKeywordTriggerEnabled`** (default `true`) — the literal word "ultracode" anywhere in a
  prompt opts that turn into the Workflow tool. This fires on a prompt *about* the setting
  ("make it ultracode by default") just as readily as on a request to use it; the opt-in reminder is a
  keyword match, not an intent read. Set `false` to disable.
- **`workflowSizeGuideline`** — `small` (<5 agents), `medium` (default, <15), `large` (<50),
  `unrestricted`. A value in any settings file overrides the `/config` row and hides it.
- **`alwaysThinkingEnabled`** — `false` disables thinking outright; effort is then moot.
- **`fastMode`** — orthogonal. Same model, faster output; `/fast` toggles it.

## Reading the settings schema out of the binary

The CLI ships as a compiled single file, so its Zod settings schema — every key, description and enum,
including ones absent from the public docs — is recoverable but not greppable the usual way. `grep`
treats the file as binary and prints nothing useful; `strings -a` is what works:

```bash
CLI=$(readlink -f "$(command which claude)")     # ~/.local/share/claude/versions/<version>
strings -a "$CLI" | grep -oE '<key>:q\(\).{0,320}'          # a boolean key's .describe() text
strings -a "$CLI" | grep -oE '"(low|medium|high)"(,"[a-z]+")+'   # enum arrays
strings -a "$CLI" | grep -oE '.{120}<term>.{120}'           # surrounding minified code
```

Two cautions. A `which claude` that resolves to a **shell function** returns the function body, not a
path — use `command which` / `command -v -p` and `readlink -f` the result. And an enum found this way
may be one of several similar arrays; confirm which key uses it by finding that key's own schema entry
rather than assuming the widest match applies. That is exactly how the `max` asymmetry above hides: the
five-value array is present in the binary, just not on `effortLevel`.

The same schema is also printed in full by the `update-config` skill, which is the cheaper first stop
when the key is a documented one.
