# How Claude Code saves and applies a default model

Measured on Claude Code 2.1.322 (Windows and macOS) in November 2026, with the hooks reference read the same week.

## What `/model` writes

- Pressing Enter in the `/model` picker, or running `/model <name>`, switches the session **and** writes `model` into the user `settings.json`. The output says "saved as your default for new sessions".
- Pressing `s` in the picker switches this session only and writes nothing.
- The effort picker saves the same way, Enter writing a default and `s` staying session-only; its keys and their precedence are in [claude-code-effort-and-ultracode.md](claude-code-effort-and-ultracode.md).

## Who picks the change up

- Every new session starts on the saved model.
- **Other sessions already open load the changed file too.** A default saved by a mis-click in one session put an unrelated session on the expensive model at its next request after a `/clear`.
- A `model` key in a project's `.claude/settings.json` outranks the user file. The `/model` command says so when it saves: ".claude\settings.json pins <model> — that applies on restart". A project pin dedicates a folder's sessions to one model only where nothing below outranks it.
- The `ANTHROPIC_MODEL` environment variable and the `--model` flag outrank every settings file for the session they launch.
- So a project pin is dead wherever the user settings' `env` block sets `ANTHROPIC_MODEL`, as these machines' do: measured 2026-11-22, a shepherd folder pinned to `claude-fable-5-2` in its project settings ran Opus, the env value.
- A `model:` line in a skill's frontmatter moves that skill onto its model, inline or forked, even where `ANTHROPIC_MODEL` is set. Measured 2026-11-25 on Windows: a throwaway project skill carrying `model: claude-fable-5-2`, run with `MSYS_NO_PATHCONV=1 claude -p "/probe" --output-format json`, listed only `claude-fable-5-2` under `modelUsage`, both without `context: fork` and with it.
- Read the model a run used from `modelUsage` in the JSON output, never from the reply. In the inline run above the reply said `claude-opus-5-5`, the session model its system prompt names, while every token was billed to Fable.
- From Git Bash, prefix `claude -p "/<skill>"` with `MSYS_NO_PATHCONV=1`. Without it the prompt arrives as `C:/Program Files/Git/<skill>`, so no skill runs as a command and the model answers from the skill file it reads instead. A run made that way showed only Opus under `modelUsage` and looked like proof that the field does nothing.

## Hooks cannot stop the save

- The `ConfigChange` hook does not run in the session that saved through `/model`. Blocking it in other sessions only stops them applying the change, and the file stays written.
- The `PreModelSwitch` hook can deny or ask, but its input does not say whether the choice is being saved, so it cannot tell Enter from `s`.
- The `PostModelSwitch` hook runs once the save is on disk, and no hook fires for an effort-only change. The measurement, with the payload fields and what restoring the file does to open sessions, is the 2026-11-19 entry in the findings log of `~/.claude/skills/hooks/SKILL.md`.
