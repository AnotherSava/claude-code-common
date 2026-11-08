---
created: 2026-10-01 15:01:43
---

# Sweep the ~40 positional cross-references CLAUDE.md's prose rule now forbids

CLAUDE.md's Prose Style paragraph now forbids pointing at a position inside a document — "the bullet above", "the section below" — and requires naming the target instead. The rule shipped in commit 0b30157 with pre-existing violations throughout the repo.

A grep for `the (bullet|section|rule|step|table|paragraph|line) (above|below)` found roughly 40, concentrated in claude/learnings/ and claude/memory/, with a handful in claude/skills/ (docs-relevance, github-pages, memo, commit).

Leave the four convention version READMEs alone — the authoring rules freeze a shipped version's text.

Each fix names the target the way claude/skills/adopt/SKILL.md reads after that commit: "the record conflict this section ends with" rather than "the record conflict below", and "the behind-its-upstream gate" rather than "the gate above".

Found by the /docs-relevance fork while it reviewed 0b30157. The sweep was kept out of that commit deliberately, to keep it to one subject.

## Still open after the first pass (2026-11-08)

The first pass fixed the hits of the grep quoted in this memo, and review found that grep too narrow: it is case-sensitive, so it misses every sentence-initial "The … above", and it lists only six nouns, so it misses "the trap above", "the case above", "(above)" and "(see above)"/"(see below)". Review fixed the instances it named in files the pass had touched; the rest remain, in edited and untouched files alike — adversarial-review-workflows.md, documentation-screenshot-staleness.md, jellyfin-watch-state-api.md, restic-backblaze-b2-backups.md, tailscale-docker-caddy-gating.md and chrome-extension.md among them.

A wider pattern, run case-insensitively over claude/learnings, claude/memory, claude/skills and README.md:

    grep -rniE '\b(the|this|that|these|those|every|each|all) ([a-z-]+ ){0,2}(above|below)\b|\beverything (above|below)\b|\((see )?(above|below)\)|(as|see) (above|below)\b'

That pattern reads one line at a time, so a pointer wrapped across a line break ("the check" ending one line, "above" starting the next) never matches it. claude/learnings/git-stash-pull-safety.md has four of those — two wrapped right before the direction word ("tell" / "above is per-file", "check" / "above is per-document") and two wrapped between determiner and noun ("The stash-SHA" / "baseline below", "the" / "assertion above") — plus "every instrument above" and "Everything above assumes" that the quantifier terms now catch. Wrapped bullets continue on an indented line, which hides two more: claude/learnings/intellij-plugin-development.md ("the upgrade chain" / "  below.") and claude/learnings/mutation-testing-vacuous-tests.md ("The copy-and-restore" / "  above has a sting"). A second pass catches the wrapped ones, allowing leading whitespace and up to two words ahead of the direction word:

    grep -rniE '^\s*([a-z-]+ ){0,2}(above|below)\b'

That pattern matched 102 lines on 2026-11-08, many of them single-line pointers the first pattern already lists, so read each hit with the line before it (`-B1`). Its hits need judgment one by one: "printed above" about terminal output, a table cell saying "same as above", "every key below the offending line" about a file's lines, and "everything above it" about a commit list are not document cross-references and stay. Three hits were kept on purpose in the first pass: wrap-up's Pending-memos probe error message (the stderr line printed above it on screen), claude/CLAUDE.md's remote-check bullet (the git log output printed below FETCH-FAILED), and the Prose Style paragraph quoting the banned phrases.
