# How Claude Code saves and applies a default model

Measured on Claude Code 2.1.322 (Windows and macOS) in November 2026, with the hooks reference read the same week.

## What `/model` writes

- Pressing Enter in the `/model` picker, or running `/model <name>`, switches the session **and** writes `model` into the user `settings.json`. The output says "saved as your default for new sessions".
- Pressing `s` in the picker switches this session only and writes nothing.
- The effort picker saves the same way, Enter writing a default and `s` staying session-only; its keys and their precedence are in [claude-code-effort-and-ultracode.md](claude-code-effort-and-ultracode.md).

## Who picks the change up

- Every new session starts on the saved model.
- **Other sessions already open load the changed file too.** A default saved by a mis-click in one session put an unrelated session on the expensive model at its next request after a `/clear`.
- A `model` key in a project's `.claude/settings.json` outranks the user file. The `/model` command says so when it saves: ".claude\settings.json pins <model> — that applies on restart". That makes a project pin the way to dedicate a folder's sessions to one model.
- The `ANTHROPIC_MODEL` environment variable and the `--model` flag outrank every settings file for the session they launch.

## Hooks cannot stop the save

- The `ConfigChange` hook does not run in the session that saved through `/model`. Blocking it in other sessions only stops them applying the change, and the file stays written.
- The `PreModelSwitch` hook can deny or ask, but its input does not say whether the choice is being saved, so it cannot tell Enter from `s`.
- The `PostModelSwitch` hook runs once the save is on disk, and no hook fires for an effort-only change. The measurement, with the payload fields and what restoring the file does to open sessions, is the 2026-11-19 entry in the findings log of `~/.claude/skills/hooks/SKILL.md`.
