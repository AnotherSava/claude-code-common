---
name: feedback_assert_the_syntax_not_the_spelling
description: A check asserting a construct is absent must match its syntax, not its spelling — the file's own warning against it contains the word
metadata:
  type: feedback
---

When a check asserts a construct is **absent**, anchor it to that construct's syntax, never to its spelling. A well-written file explains why the forbidden thing is forbidden, so a substring search finds the explanation and fails the file that heeds it.

**Why:** on 2026-08-30 a test asserted a systemd drop-in contained no `WatchdogSec=`, written as `"WatchdogSec" in text`. The file's header explains at length why `WatchdogSec` would SIGABRT the daemon — so the check failed on the comment written to prevent the mistake, and the better-documented the file, the more certainly it failed. `re.search(r"^\s*WatchdogSec\s*=", text, re.M)` is the honest form. What makes it a rule rather than a one-off: the same repo already carried a named test case for exactly this shape on a different linter — *"a comment naming a construct it does not contain"* — and it was reintroduced anyway, in a new check, by someone who had read that case.

**How to apply:** an absence check matches a directive, a declaration, a call — something with syntax. `^\s*KEY\s*=`, a parsed AST, the config format's real reader. Strip comments first where the format has them, which is what a parser would do anyway. Then prove it fires: feed the checker a file that genuinely contains the construct, because a check that can only pass is indistinguishable from no check at all. The same reasoning applies to the inverse — asserting a construct is *present* by substring will happily match a comment saying it was removed. Related: [[feedback_grep_markdown_emphasis]] (the same naive-pattern failure while *searching* rather than asserting) and [[feedback_not_run_is_not_pass]].
