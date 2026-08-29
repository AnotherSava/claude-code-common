---
name: feedback_uncommitted_is_not_delivered
description: A fix sitting in a working tree is not a delivered fix; check the committed and pushed side before calling anything handled
metadata:
  type: feedback
---

Before reporting a problem fixed — or a backlog item closed — check the state that **other machines and other runs actually see**, not the one in front of you. On a repo whose working tree you have been editing, `git show HEAD:<path>` and `git log @{upstream}..HEAD` answer a different question from `cat <path>`, and it is the one that matters.

**Why:** on 2026-08-28 a triage of seven backlog items returned five "already handled" verdicts, and every one was overturned. Three hinged on the same mistake: fixes to `ingress-lint.py`, `git/gitignore` and a publish skill existed as unstaged bytes in one Mac working tree, while `HEAD == origin/main` at a commit that contained none of them. Because `~/.claude` symlinks into that dotfiles repo and the user works from a Windows machine too, **the commit is the distribution mechanism** — so the Windows machine was still running the old duplicated linter with three known hijack blindspots live. "Written" and "in effect everywhere" were a day and a push apart. The reading is seductive because the file on disk is genuinely correct; nothing about `cat` looks like a shortcut.

**How to apply:** when judging whether something is done, say which side you looked at. For a repo other machines pull, check `HEAD` and the upstream ref rather than the file — and remember that a tool symlinked out of a repo is distributed by commits, so editing it changes exactly one machine until it is pushed. The same gap exists wherever a publish step sits between authoring and use: a built asset, a deployed config, a released package, a skill under `~/.claude/`. Related: [[feedback_state_the_enforcement_reach]] (never conclude more broadly than the check you cite delivers) and [[feedback_not_run_is_not_pass]].
