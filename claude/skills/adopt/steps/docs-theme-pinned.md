---
version: 11
slug: docs-theme-pinned
title: The docs theme is pinned to a tag
scope: repo
---

# The docs theme is pinned to a tag

A `remote_theme` written without an `@<ref>` suffix resolves to the theme repository's default
branch on every rebuild, which the Pages build log records as
`Downloading .../just-the-docs/zip/HEAD`. The version serving the site is therefore not knowable
from this repo and moves under it with nothing committed here. A layout the pages depend on can
change that way. So can whether a local override still reaches the theme: Jekyll resolves
`_includes/nav_footer_custom.html` and the `_sass/` overrides against the theme's own files of
those names, so which version is serving decides whether the override reaches the file it
shadows. Nothing triggers the change either, so the breakage first shows up on the next
unrelated docs edit and reads as though it came from whatever was touched that day.

The tag to pin to is a constant the author of this step resolved, and this is where it is
written down:

```yaml
remote_theme: just-the-docs/just-the-docs@v0.12.0
```

The `apply` command reads that value back out of this file rather than asking GitHub for it. A
step never touches the network, and a value a script cannot resolve is one it must not guess —
so the tag lives in a single place, the prose the user reads while walking this step, and a
later bump is a one-line edit here with nothing to keep in sync. Resolve a newer one with
`gh api repos/just-the-docs/just-the-docs/releases/latest --jq .tag_name`, and read the
`github-pages` skill before bumping: the theme's releases run months behind its default branch,
so a pin moves a site backwards from HEAD rather than forwards.

## Applies when

This repo's `docs/_config.yml` sets `remote_theme` to `just-the-docs/just-the-docs` with nothing
after it. That one line is rewritten to carry the tag above, with a short note inserted over it
saying what the missing ref did. Nothing else in the file is touched, and the run proves it:
every other line is read back off disk and compared against what was there before.

## Does not apply when

There is no `docs/_config.yml`. That is positive evidence about the convention's own
precondition — this repo publishes no Jekyll site, and this step never creates one. The absence
differs from v1's in exactly that respect: a backlog directory is where memos are required to
go, so a repo with no backlog file has not thereby been shown to want none, whereas nothing
requires a repo to publish docs at all.

The theme is already pinned and the rest of the shape holds. Verify sees that first and records
the repo as in the target shape with no mutation, which is what makes a first record cost
nothing in a repo pinned before this step existed; probe repeats the same reading for anyone who
runs it directly.

## Cannot tell

Four states, each asking something different:

- **A different theme is named.** chrome-assistant sets `theme: jekyll-theme-hacker`, a
  gem-based theme rather than a remote one. A divergence chosen on purpose and a site nobody has
  migrated read identically from the file, so this is a question: is that theme deliberate —
  record `n/a` — or should the site move to `just-the-docs`, which is a rewrite of the whole
  site's styling and a human's job, not this step's.
- **No theme key at all.** Neither `remote_theme` nor `theme` appears, so the site is served by
  whatever Jekyll defaults to and this step has no line to pin. Name the theme the site should
  use and re-run.
- **Two `remote_theme` keys, or one nested under another key.** Which value Jekyll ends up using
  is not this step's guess — a duplicate key resolves to the last one, so rewriting the first
  would leave the site unpinned while the file claims otherwise. Both lines are printed verbatim
  with their line numbers; delete the wrong one and re-run.
- **The theme is pinned, but another half of the shape is missing** — `plugins` does not list
  `jekyll-remote-theme`, or `docs/index.md` or `docs/pages/` is absent. Verify fails on that
  repo and this step will not write any of it, because a plugins list and a page tree are the
  `github-pages` skill's to build. The question names which half is missing.

A file that exists and will not open at all is not one of those. That is an error rather than a
question, because nothing about the site was observed.

## Fetch before running

This step rewrites `docs/_config.yml`, a committed file the other machine may have edited — and
a rewrite of one line merges cleanly against an edit to another, so a stale tree loses nothing
visibly. The `/adopt` procedure refuses to start on a branch behind its upstream, which is the
gate that matters here (`learnings/git-stash-pull-safety.md`).

Afterwards, `git diff @{upstream} -- docs/_config.yml` should show exactly the one changed line
and the note above it. Anything else in that diff came from the other machine and is worth
reading before committing.

## Verify

The question is whether this repo is in the shape the convention requires, never whether a pin
was written here. So the assertion is read off the file rather than off a history: exactly one
`remote_theme` key at the top level of `docs/_config.yml`, naming `just-the-docs/just-the-docs`
with an `@<ref>` after it; `jekyll-remote-theme` listed under `plugins`, without which Jekyll
never loads the plugin that reads the key at all; and `docs/index.md` and `docs/pages/` both
present, so the pin is asserted about a site that exists.

It asserts that a pin exists and never which tag. A verify keyed on today's value would turn
every adopted repo into an audit failure the day the theme releases again, and the point of the
pin is that it holds until somebody moves it deliberately.

It cannot pass vacuously. A tree with no `docs/_config.yml` is exit 2 and never exit 0: a repo
publishing no site has no `remote_theme` whose pinning could be true or false, so the shape is
unobservable rather than satisfied, and a verify that passed there would hand the whole fleet a
free line for a convention nobody checked. Probe is what then files those repos as `n/a`, with
the positive evidence behind it.

The same exit covers the other unobservable case: a `docs/_config.yml` that is on disk and will
not open.

## By hand, after the script

- Confirm the Pages build succeeded before believing the change took effect. A failed build
  keeps serving the previous deploy, which reads exactly like a change that did nothing, so
  check the `pages build and deployment` run and then the published page — never the source.
- Read the site once at the new pin. The theme's releases run months behind its default branch,
  so pinning moves the site backwards: an include, a variable default or a class name the pages
  rely on from recent theme source may not exist at this tag.
- Check the attribution footer is still suppressed. Whether `_includes/nav_footer_custom.html`
  reaches the theme's fallback depends on which version is serving, which is the thing the pin
  makes stable — it is not the thing the pin supplies, and this step asserts nothing about it.
- Bump the tag deliberately, like a dependency, by editing the fenced line above. Nothing in
  this system re-checks whether a repo's pinned tag is the current one, on purpose: the
  alternative is a fleet-wide false alarm on every theme release.
