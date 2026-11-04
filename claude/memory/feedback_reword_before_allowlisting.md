---
name: feedback_reword_before_allowlisting
description: A blocking confidentiality-scan finding is cleared by rewording the text where possible; an allow-list entry is the last resort
metadata:
  type: feedback
---

When the commit privacy scan (`scan-commit-confidentiality.py`, run by `shared/commit.py`) blocks on a finding, first try to reword the flagged text so it no longer carries the term — "the production box" instead of the host's name — and propose the allow-list entry in `.claude/confidentiality-allow` only when the term genuinely has to stay.

**Why:** asked on 2026-11-04 whether to allow a host name in a reworded README sentence or reword it, the user answered "allow, but try to avoid when you can". Each allow entry is a permanent exemption, and the allow file grows as a list of things nobody re-reads.

**How to apply:** when the scan blocks, check whether the sentence still says what it needs to without the term. If it does, reword it and recommend that. Otherwise, offer the allow entry with a comment saying why the term has to stay.
