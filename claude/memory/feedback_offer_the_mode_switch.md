---
name: feedback_offer_the_mode_switch
description: When the permission classifier refuses several steps of one task, offer switching the session's permission mode instead of handing commands over one at a time
metadata:
  type: feedback
---

When the permission classifier refuses several steps of one task, offer to switch the session's permission
mode before handing commands over one at a time. Auto mode decides without asking; `manual` turns the same
refusals into approve/deny prompts, keeping every gate while letting the work proceed.

**Why:** On 2026-10-06 four classes of command were refused — `ssh` to anything under `/etc/<app>/`, and
every Doppler call that returns a value. I handed over one command, then a second, then re-asked for
permission rules, across three round trips. The user asked "can you do it in non auto-mode?" and the whole
sequence then ran unattended. A chat approval cannot lift a classifier gate, so repeating the ask was never
going to work, and the denial message says as much: it names the auto-mode classifier and points at a
settings rule.

**How to apply:** After the second refusal inside one task, name the mode switch as an option alongside the
per-command handover, and say which gates it keeps. Read the modes from `claude --help` rather than recall —
`--permission-mode` lists them. Never propose `bypassPermissions` or `dontAsk`: those remove the gate rather
than handing it to the user, which is the opposite of what the refusal is asking for. Changing the mode is
the user's to do; never edit permission settings to clear your own block, and never route the blocked work
to a peer session, which is [[peer_messaging]]'s laundering case.

Related: [[feedback_route_output_not_paste]] for how to hand a command over when that is still the right
move, and [[feedback_keep_your_half]] for what genuinely belongs to the user.
