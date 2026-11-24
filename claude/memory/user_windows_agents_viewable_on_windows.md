---
name: user_windows_agents_viewable_on_windows
description: the Windows box's agents must stay viewable from Windows; a design that leaves them viewable only from the Mac is a blocker
metadata:
  type: user
---

The agents running on the Windows box must stay viewable from Windows itself, through Windows Terminal attached to their WSL tmux sessions. A setup that moves them somewhere only the Mac can show is a blocker, however much it improves the Mac's view.

**Why:** on 2026-11-24 the user declined running agterm-server in WSL. It would have made those agents native agterm sessions on the Mac, but agterm-server's sessions can only be viewed from a Mac.

**How to apply:** when weighing a feature that changes where the Windows agents run or how they are reached, check first that Windows can still show them. Raise a Mac-only view as the blocker up front instead of researching around it. Related: [[feedback_agterm_agwinterm_parity]].
