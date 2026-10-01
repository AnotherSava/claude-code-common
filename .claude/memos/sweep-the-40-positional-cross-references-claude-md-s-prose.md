---
created: 2026-10-01 15:01:43
---

# Sweep the ~40 positional cross-references CLAUDE.md's prose rule now forbids

CLAUDE.md's Prose Style paragraph now forbids pointing at a position inside a document — "the bullet above", "the section below" — and requires naming the target instead. The rule shipped in commit 0b30157 with pre-existing violations throughout the repo.

A grep for `the (bullet|section|rule|step|table|paragraph|line) (above|below)` found roughly 40, concentrated in claude/learnings/ and claude/memory/, with a handful in claude/skills/ (docs-relevance, github-pages, memo, commit).

Leave the four convention version READMEs alone — the authoring rules freeze a shipped version's text.

Each fix names the target the way claude/skills/adopt/SKILL.md reads after that commit: "the record conflict this section ends with" rather than "the record conflict below", and "the behind-its-upstream gate" rather than "the gate above".

Found by the /docs-relevance fork while it reviewed 0b30157. The sweep was kept out of that commit deliberately, to keep it to one subject.
