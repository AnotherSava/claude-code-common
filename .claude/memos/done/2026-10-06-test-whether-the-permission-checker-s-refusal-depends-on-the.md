---
created: 2026-10-06 23:16:36
---

# Test whether the permission checker's $() refusal depends on the session's permission mode

A Context `!` line containing $() is refused before a skill loads — "Shell command permission check failed … Contains command_substitution" — and the refusal aborts the whole skill load. But it does not happen to every session, and the discriminator has never been isolated.

The hypothesis to test, raised by the user on 2026-10-06: it depends on the permission mode, auto versus manual/prompting.

Evidence already in hand, none of it conclusive:

- Two sessions hit the refusal on `/commit` the same day (printlab, landlord) and a third (printlab again) hit a different refusal on `/publish`'s `git remote get-url origin … || echo none` probe — "This Bash command contains multiple operations. The following part requires approval".
- Every cross-session message from both of those sessions carried `from-mode="prompting"` in its relay header.
- This repo's `claude/settings.json` sets `permissions.defaultMode: "auto"`, and the dotfiles session invoked `/commit` repeatedly the same day with the $() lines in place and never saw a refusal.
- `claude/memory/feedback_offer_the_mode_switch.md` already records that repeated classifier refusals in one task are answered by offering a switch to `manual` — so a classifier that refuses commands is known to be mode-sensitive. That is the same classifier by description, which is what makes the hypothesis worth testing rather than guessing.

What would settle it: invoke one skill whose Context carries a $() probe from the same repo under each mode and compare. `claude/learnings/skill-context-evaluator.md` is the write-up's home — its section already says the discriminator is not isolated and lists the shapes that survive (an assignment, a quoted argument value) against the one that does not (a bare argument), so the answer belongs there rather than in a new file.

Why it matters beyond curiosity: `claude/skills/skill/SKILL.md` states a blanket ban on $() in Context lines, and `claude/skills/commit/SKILL.md` currently has five such lines that load fine. A rule with five working counterexamples in one file cannot tell the next author which form is safe, and the cost of being wrong is a skill that does not run at all.

May be closed without work if landlord's uncommitted section in skill-context-evaluator.md ends up recording the mode — it was being written while this was captured.
