# How Jekyll matches an `exclude:` entry

An `exclude:` entry in `_config.yml` looks like a path pattern and is not quite one. GitHub Pages
builds with Jekyll 3.10, which joins each entry onto the source directory with Ruby's `File.join`
and then compares by prefix. `File.join` normalises nothing, so two spellings that read as
equivalent behave differently, and one of them excludes nothing at all.

Established 2026-09-27 by reading Jekyll 3.10.0's `glob_include?` and running the match in Ruby 3.3,
with `docs/` as the source and a directory `screenshots/raw/` to keep off the site:

| entry | effect |
|---|---|
| `screenshots/raw/` | excludes the directory — the form to use |
| `/screenshots/raw/` | the same: `File.join` collapses the doubled slash |
| `./screenshots/raw/` | **excludes nothing** — the `./` survives the join and matches no path |
| `screenshots/raw` | excludes the directory **and every sibling whose name starts `raw`**, such as `screenshots/raw-formatted.png`, because the match is a prefix |

So write the directory with a trailing slash, never with `./`, and never bare when a sibling could
share the prefix. The failure modes are both silent: the build succeeds, and either the files you
meant to hide are published or a page's image disappears from the site.

Two checks that settle it on a real site, since a config that reads right proves nothing: after the
Pages build succeeds, request a file under the excluded directory and expect 404, and open a page
embedding a sibling with the shared prefix and expect the image. A failed build keeps serving the
previous deploy, so confirm the build before believing either.

The conventions rule `screenshot-raws-unpublished` encodes this for `docs/screenshots/raw/`.
