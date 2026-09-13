---
name: feedback_keep_your_half
description: When splitting a task with the user, hand back only the part that needs a human — the analysis stays mine
metadata:
  type: feedback
---

When a task has to be split between the user and me, hand back only the part that genuinely needs a human: an action at their own keyboard, a judgement that is theirs, a value only they hold. Everything downstream of it — reading the log, correlating the evidence, deciding what it shows — stays mine, and offering to teach them how to do it is a way of giving them my half.

**Why:** verifying a player fix needed a real browser, so I correctly asked the user to close the dialog a second into a resumed play — then closed with "want me to walk through what to look for in the Jellyfin log afterwards?". They answered: "won't it be you looking in the log?" It was. The split was right and the closing line handed back the wrong side of it, which reads as work being pushed at them under the guise of help.

**How to apply:** state their action, then say what I will do with the result — "play something with a resume point and close the dialog about a second in; I will check whether any ffmpeg job appears after the stop". Never describe how they should interpret an artifact I can read myself. This is the closing-ask form of [[feedback_use_the_tool_you_built]]'s parent rule in **Self-Sufficiency**: before handing over any step, ask whether I could just do it.
