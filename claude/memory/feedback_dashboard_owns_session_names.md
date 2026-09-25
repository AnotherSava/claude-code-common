---
name: feedback_dashboard_owns_session_names
description: The dashboard owns user-facing session names and tab titles; a shell wrapper around claude must not set either
metadata:
  type: feedback
---

Do not add `--name` or an OSC title write to a shell wrapper around `claude`. Both were removed from
the Mac's `claude()` on 2026-09-21 rather than being ported to the Windows machine's, which had never
had them.

**Why:** the dashboard already names each session and colours its terminal tab, which is the whole
reason those wrappers export `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` — it stops Claude's own per-tick
title writes from clobbering what the dashboard put there. A wrapper writing its own name or title
duplicates that work and then competes with it. Claude's internal session name is not worth managing.

**How to apply:** a wrapper decides *behaviour* — resume versus fresh, which binary runs, which
environment is set — and leaves naming and titling alone. The specific temptation this rules out is
reaching for `--name "${PWD##*/}"` so sibling agents can address the session by a stable name:
cross-machine addressing goes through the dashboard, which keys on the project directory rather than
on that name. See [[dashboard_agent_roster]] for what it does key on, and [[peer_messaging]] for
reaching a session once it is found.

A wrapper may still carry the dashboard's title to a terminal that would otherwise lose it, since
that serves the dashboard rather than competing with it. `remote_session_attach` in
`claude/remote-session/lib.sh` is that case: tmux forwards a pane's title only with `set-titles`,
so it turns that on with a format that passes the title verbatim, adds a fixed `⇄` for a client on
another machine, and blanks the title with an empty OSC 0 when tmux returns, because Windows Terminal
ignores tmux's request to restore the old one. Inside tmux the `CLAUDE_CODE_DISABLE_TERMINAL_TITLE`
export has to be in the pane's own command (`remote_session_resume_command`), because the wrapper's
environment never reaches the pane. What stays ruled out is a name or status the wrapper composes.

An argument the user types still passes through, and always did — this is about what a wrapper adds
on its own, never about filtering what was asked for.
