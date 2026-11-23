# Claude Code status line: what reaches the command, and the row it keeps

A status line is the one documented place to show per-session state under the prompt, so it is the first idea for
anything conditional, such as naming the model only when it is not the default. Conditional is what it does badly:
under the fullscreen renderer the row stays on screen whether or not the command prints anything.

## An empty status line still takes a row in fullscreen

**Remove the `statusLine` entry to get the row back; empty output does not.** With `"tui": "fullscreen"`, a command
that prints a bare newline and one that prints zero bytes both leave a blank row between the prompt and the footer.
Taking the entry out of `settings.json` removes the row. Measured 2026-11-23 on Claude Code 2.1.322, Windows.

No setting collapses it: the documented fields are `type`, `command`, `padding`, `refreshInterval` and
`hideVimModeIndicator`. anthropics/claude-code#83402 reports the same and reads the renderer as forcing a blank row
only in fullscreen, with the classic renderer (`/tui default`, or `CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN=1`)
rendering nothing for empty output. That half was not measured here. The issue was closed as not planned for
inactivity on 2026-09-21. `/tui` switches renderer by restarting the session in place.

So a status line that should appear only sometimes is not available under fullscreen. A hook that adds and removes
the entry is not a way round it either: the user settings file is shared by every session, so one session's state
would put the row into all of them.

## What the command receives and runs under

- **A settings edit applies live.** Adding or changing `statusLine` in `settings.json` took effect in the running
  session at its next conversation event, with no restart.
- **The `env` block reaches it.** The command saw `ANTHROPIC_MODEL=opus` from the user settings' `env`, so a script
  can compare the session's model with the configured default.
- **It runs through bash on Windows.** `$HOME`, a pipe and `tee` into a relative path all worked; the working
  directory was the session's.
- **Payload fields.** `model.id` (`claude-opus-5-5`) and `model.display_name` (`Opus 5.5`), beside top-level
  `context_window`, `cost`, `cwd`, `effort`, `exceeds_200k_tokens`, `fast_mode`, `output_style`, `prompt_cache`,
  `prompt_id`, `rate_limits`, `session_id`, `thinking`, `transcript_path`, `version` and `workspace`. Captured
  2026-11-23 by putting `tee` in front of the script.

Leave `refreshInterval` unset on Windows: the spawn cost of a timed status line in every session is in
`skills/hooks/references/performance.md`. Without it the command runs only on conversation events, debounced 300 ms.
