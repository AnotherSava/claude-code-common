---
title: The docs theme is pinned to a tag
rules: docs-theme-pinned
---

## What changed

A `remote_theme` written without an `@<ref>` suffix resolves to the theme repository's default
branch on every rebuild, which the Pages build log records as
`Downloading .../just-the-docs/zip/HEAD`. The version serving the site is therefore not knowable
from this repo and moves under it with nothing committed here. A layout the pages depend on can
change that way. So can whether a local override still reaches the theme: Jekyll resolves
`_includes/nav_footer_custom.html` and the `_sass/` overrides against the theme's own files of those
names, so which version is serving decides whether the override reaches the file it shadows. Nothing
triggers the change either, so the breakage first shows up on the next unrelated docs edit and reads
as though it came from whatever was touched that day.

The tag, resolved when this version was written:

```yaml
remote_theme: just-the-docs/just-the-docs@v0.12.0
```

A version folder is immutable — repos run it at different times and must get the same behaviour from
one number — so a later bump is an ordinary dependency bump in the repo whose site it is, editing
that repo's `docs/_config.yml` and nothing here. Resolve a newer tag with
`gh api repos/just-the-docs/just-the-docs/releases/latest --jq .tag_name`, and read the
`github-pages` skill before bumping: the theme's releases run months behind its default branch, so a
pin moves a site backwards from HEAD rather than forwards.

## Migrating an existing repo

There is work here when this repo's `docs/_config.yml` sets `remote_theme` to
`just-the-docs/just-the-docs` with nothing after it. Rewrite that one line to carry the tag above,
with a short note inserted over it saying what the missing ref did. Touch nothing else in the file,
and prove it: read every other line back off disk and compare it against what was there before.

Fetch first, and do not run this on a branch behind its upstream: the rewrite touches
`docs/_config.yml`, a committed file the other machine may have edited, and a rewrite of one line
merges cleanly against an edit to another, so a stale tree loses nothing visibly
(`learnings/git-stash-pull-safety.md`).

Four states are a question for the user rather than work to do:

- **A different theme is named.** chrome-assistant sets `theme: jekyll-theme-hacker`, a gem-based
  theme rather than a remote one. A divergence chosen on purpose and a site nobody has migrated read
  identically from the file, so ask: is that theme deliberate, or should the site move to
  `just-the-docs`, which is a rewrite of the whole site's styling and a human's job?
- **No theme key at all.** Neither `remote_theme` nor `theme` appears, so the site is served by
  whatever Jekyll defaults to and there is no line to pin. Ask which theme the site should use.
- **Two `remote_theme` keys, or one nested under another key.** Which value Jekyll ends up using is
  not this version's guess — a duplicate key resolves to the last one, so rewriting the first would
  leave the site unpinned while the file claims otherwise. Print both lines verbatim with their line
  numbers and ask for the wrong one to go.
- **The theme is pinned, but another half of the shape is missing** — `plugins` does not list
  `jekyll-remote-theme`, or `docs/index.md` or `docs/pages/` is absent. Write none of it: a plugins
  list and a page tree are the `github-pages` skill's to build. Name which half is missing.

A `docs/_config.yml` that exists and will not open at all is not one of those. That stops the work,
because nothing about the site was observed.

What the rewrite changes, and how to compare it: `git diff @{upstream} -- docs/_config.yml` should
show exactly the one changed line and the note above it. Anything else in that diff came from the
other machine and is worth reading before committing.

Afterwards:

- Confirm the Pages build succeeded before believing the change took effect. A failed build keeps
  serving the previous deploy, which reads exactly like a change that did nothing, so check the
  `pages build and deployment` run and then the published page — never the source.
- Read the site once at the new pin. The theme's releases run months behind its default branch, so
  pinning moves the site backwards: an include, a variable default or a class name the pages rely on
  from recent theme source may not exist at this tag.
- Check the attribution footer is still suppressed. Whether `_includes/nav_footer_custom.html`
  reaches the theme's fallback depends on which version is serving, which is the thing the pin makes
  stable — it is not the thing the pin supplies, and nothing here asserts it.

## When it does not apply

There is no `docs/_config.yml`. That is positive evidence about the convention's own precondition —
this repo publishes no Jekyll site, and none is created here. The absence differs from the memos
one's in exactly that respect: a backlog directory is where memos are required to go, so a repo with
no backlog file has not thereby been shown to want none, whereas nothing requires a repo to publish
docs at all.

The theme is already pinned and the rest of the shape holds is the other case, and reading it that
way is what makes a first record cost nothing in a repo pinned before this version existed.

## Continuing rule

`docs-theme-pinned` — exactly one `remote_theme` key at the top level of `docs/_config.yml`, naming
`just-the-docs/just-the-docs` with an `@<ref>` after it; `jekyll-remote-theme` listed under
`plugins`, without which Jekyll never loads the plugin that reads the key at all; and
`docs/index.md` and `docs/pages/` both present, so the pin is asserted about a site that exists. It
asserts that a pin exists and never which tag — keyed on today's value it would fail every adopted
repo the day the theme releases again, and the point of the pin is that it holds until somebody
moves it deliberately.
