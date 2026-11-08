# Turning off Claude Code's agent view

Agent view is the screen that lists background conversations (Needs input, Completed). The Left
arrow on an empty prompt opens it. In a session started in the terminal, that also moves the
conversation to the background. Picking a row there then puts a different conversation in the same
tab, and the tab's title changes to match it.

Two switches control it. They live in different files, and no keybinding controls either one.

| Goal | Setting | Where |
|---|---|---|
| Turn off only ← (keep `claude agents`, `--bg`, `/background`) | `"leftArrowOpensAgents": false`, or the **← opens agents** row in `/config` | `~/.claude.json` (global config). `settings.json` ignores this key |
| Turn off agent view and background sessions entirely | `"disableAgentView": true`, or `CLAUDE_CODE_DISABLE_AGENT_VIEW=1` | any settings file; managed settings enforce it |

The full switch disables `claude agents`, `--bg`, `/background` and the daemon that runs background
conversations. The binary still parses those words and refuses them itself ("'agents --json' is
disabled by the 'disableAgentView' setting"), so a wrapper that routes them to `claude.exe` should
keep routing them. Ordinary sessions, `--resume`/`--continue`, subagents and messages between sessions
keep working. It takes effect only in sessions started after the change. Sessions already running
keep the Left key until they restart.

Background sessions already running when the switch goes on are left without a clean way out. Measured
2026-11-04 on Windows: `claude stop <jobId>` was refused ("'stop' is disabled by the 'disableAgentView'
setting"), and `taskkill /T /F` on a background session's `claude.exe` brought it back within seconds
under a new PID with the same `sessionId` and `jobId`. One of two such sessions stayed dead after its
kill and the other came back, so what decides which one is restarted is not known.

`~/.claude/keybindings.json` cannot unbind ←. The keybindings reference names no action for it, so
setting `"left": null` in a context does nothing to this behaviour.

`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` is a different switch. It stops background shell commands and
subagent runs, and leaves background sessions untouched.

Source: the Claude Code docs pages agent-view, settings-reference (`leftArrowOpensAgents`,
`disableAgentView`), env-vars and keybindings, read 2026-11-04. The docs don't say outright that
`disableAgentView` also stops ← parking, though it follows from ← opening agent view.
