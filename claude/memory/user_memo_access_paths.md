---
name: Memos are reached through the wrapper and the skill, never the CLI
description: the memo backlog is used via the `memo` shell function and the /memo skill; memos.py is not typed by hand, so invest in those two surfaces
metadata:
  type: user
---

The memo backlog has two surfaces in daily use, and the script under them has none. The `memo`
shell function — bash and PowerShell, documented in `learnings/shell-environment.md` — is the
model-free path, and it only ever calls `add` and `list`. Everything else (`done`, `reopen`,
`show`, `path`, `drop`) arrives through the `/memo` skill, which is where the model does the
typing. `memos.py` is not invoked by hand.

So weigh work on the backlog accordingly. A defect in the wrapper is on the path used every day —
which is what makes the silent comma and backtick corruption in the PowerShell half worth fixing
rather than documenting. Prose in `SKILL.md` is read by the model on every review, so it is the
place a rule actually takes effect. A usage line in the module docstring is reference material for
whoever is reading the source, not an interface anyone operates: correct, and not where ergonomics
belong.

Related: [[feedback_deploy_script_not_skill]] draws the opposite conclusion for deploy and publish,
where the script *is* the daily path and the skill is first-time setup only. The two are not in
tension — which surface a tool is used through is a fact about that tool, so check rather than
assume.
