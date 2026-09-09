# Where an output rule can live

Verified against Claude Code 2.1.263 on 2026-09-08 by reading the installed binary and by running probe
styles end to end. Re-verify before relying on any capability claim here — this is a record of what was
true at that version, not a standing guarantee.

## The four mechanisms

| | Reaches | Persistence | Install cost |
|---|---|---|---|
| **Output style** | main thread, forks, teammates — **not** Task subagents | in the system prompt, plus a per-turn "a style is active" nudge | one file, one settings key, one symlink |
| **CLAUDE.md** | most subagents (`Explore`, `Plan` and the web-fetch agent skip it) | re-read at launch and after compaction | none, already symlinked |
| **`~/.claude/rules/`** | same as CLAUDE.md | same as CLAUDE.md | one symlink |
| **SessionStart hook** | main thread | one deduped message that ages backward | a script per platform, plus a settings entry |

## Why an always-applies shape rule belongs in an output style

CLAUDE.md is **not** system-prompt level. It arrives as a user message, and the harness wraps it with:

> IMPORTANT: this context may or may not be relevant to your tasks. You should not respond to this context
> unless it is highly relevant to your task.

That hedge is aimed at project context, but it lands on everything in the block. An output style instead
replaces the system prompt's opening line — the model is told it "helps users according to your Output Style
below" — so a rule about how to reply arrives as what the model *is*, not as context that might be irrelevant.

The upstream skill that prompted this research needed a `## Persistence` section, a flag file and three
platform hook scripts to approximate what an output style does with a frontmatter key. A skill body is
injected once and drifts backward through the conversation; that is the problem those workarounds solve, and
the problem output styles do not have.

## Four things that fail quietly

1. **`keep-coding-instructions` defaults to `false`.** Omitting it from a custom style's frontmatter silently
   drops Claude Code's built-in software-engineering instructions — how to scope a change, when to comment,
   how to verify. Nothing warns. Every custom style here must set it to `true`.
2. **An unknown style name is a no-op with exit 0.** The settings schema accepts `outputStyle` as an
   unvalidated free string, and no diagnostic for a missing style exists in the binary. A style file that did
   not get symlinked on one machine produces a session that looks completely normal and applies nothing. Check
   the style is live rather than assuming it — the preflight script does this.
3. **Output styles stop at Task subagents.** Every injection point lives in the main-thread prompt builder. A
   rule a subagent must also follow belongs in CLAUDE.md — and even that is skipped by the built-in `Explore`
   and `Plan` agents, so a rule those must obey has to be restated in the delegation prompt.
4. **The `/config` picker writes the selection project-locally**, into that project's
   `.claude/settings.local.json`. A machine-wide default has to be the `outputStyle` key in the repo's own
   `claude/settings.json`. Selecting a style through the menu therefore creates a per-project override that
   shadows the global default in that project from then on — which is a usable escape hatch, but only if
   nobody mistakes it for the global switch.

## Two built-in styles already exist

`Concise` and `Proactive` ship with the CLI. `Concise` bans the same openers a hand-written rule would
("Let me…", "Now I'll…") and closing recaps, and it carries a real per-turn reminder that restates its rule —
something a *custom* style cannot do, because the reminder text is a built-in-only field with no frontmatter
key. A custom style gets the generic "a style is active" nudge instead.

So before authoring a rule, check whether a built-in already covers it. Adoption by subtraction costs nothing
and keeps the authored file small.

## Ruled out, with reasons

- **`--append-system-prompt` / `--append-system-prompt-file`** — genuinely system-prompt level and the only
  mechanism that reaches subagents (via the `--append-subagent-*` variants). Rejected because it must be
  passed on every invocation, so installing it means a per-machine shell alias, outside this repo's symlink
  story.
- **`~/.claude/rules/`** — real and documented, and it would keep a long CLAUDE.md from growing. Rejected for
  shape rules because it rides the identical delivery channel and hedge as CLAUDE.md, so it buys separability
  and no adherence. Its `paths:` frontmatter lever is useless here: shape applies to every reply, while
  path-scoped rules fire only when a matching file is read.
- **A SessionStart hook** — what the upstream plugin does. Rejected as strictly worse than the alternatives:
  it costs a script per platform and a settings entry, and delivers a conversation message that ages backward,
  where a style costs one file and sits in the system prompt. Note this is *not* blocked by the
  no-per-prompt-hooks rule, which explicitly permits session-start hooks; it simply loses on merit.
- **CLAUDE.md `@path` imports** — the imported file still loads into context at launch, so it saves no tokens
  and inherits the same hedged delivery.
