---
name: feedback_ask_for_the_entry_point
description: Can't find the surface a request names? Ask how the user reaches it — a chord, a menu path, a URL — not which of your candidates it is
metadata:
  type: feedback
---

When a request names a UI surface and a thorough search of the repo does not find it, ask **how you get to it** — the keyboard shortcut, the menu path, the URL — rather than offering a list of candidate surfaces to choose between.

**Why:** a candidate list can only help if the answer is in it, and a search that already failed is evidence it is not. The entry point is something the user always knows, takes three characters to type, and resolves the question completely — including to code in a different repo, which no amount of grepping here could reach. 2026-10-01: "when listing remote sessions to open, do not list already open ones" survived about ten greps of the dashboard repo; three offered candidates were all wrong; the answer was `cmd+shift+r`, bound in the agterm keymap to a script in the dotfiles repo.

**How to apply:** ask the open question first, before building an options list. [[feedback_check_live_sibling_session]] is the companion — an instruction that does not fit this repo usually belongs to another one.
