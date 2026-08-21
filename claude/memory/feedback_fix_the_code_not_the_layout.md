---
name: Fix the code, don't tell the user to rearrange their files
description: When a user's real data layout defeats a feature, treat it as a defect in the feature rather than reporting a caveat plus a manual workaround
type: feedback
---

When a feature doesn't fire against the user's **actual** data, that is a defect in the feature — not a limitation to report with a manual workaround attached.

**Why:** Reporting "it won't work for your case, here's how to rearrange things" reads as a workaround for my own limitation, and it throws away the general fix for everyone else with that layout. It also inverts the usual direction of effort: the user does filesystem surgery to satisfy code that could have adapted. In the achievement-overlay project, a feature that reads a game's own config was verified against the one install that actually exercised it, and it did nothing. I reported that the game's assets sat in a folder the scanner ignored and that *moving them* would light it up. The real answer was two code changes — the scanner was skipping hidden folders (a .NET enumeration default), and it kept only one config folder per game where that game had two. Both were general bugs affecting any similarly-packaged install, and the manual workaround would have hidden them.

**How to apply:** Before writing "this won't work for your case", ask whether the code could accommodate the case. Treat a real-world layout that defeats a feature as evidence about the world rather than about the user's setup — if one install is shaped that way, others are. Only offer a manual workaround when the code genuinely can't reach the case (e.g. the data lives somewhere nothing maps to), and say plainly that it can't. Related: [[feedback_fix_at_source]] (fix at the origin, not the caller) and the Self-Sufficiency rule in the global CLAUDE.md (don't hand the user a task you could do yourself).
