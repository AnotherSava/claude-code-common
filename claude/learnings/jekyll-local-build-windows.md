# Building a GitHub Pages Jekyll site locally on Windows

Use this to check a docs-site change before pushing it. The Pages build is authoritative, and a
failed build silently keeps serving the previous deploy. A local build catches Liquid errors, broken
nav front matter and theme overrides that don't take, and it gives rendered pages to screenshot.

It is an approximation. Pages runs Jekyll 3.10. Jekyll 4.x is what installs cleanly on current
Ruby, so read the local result as "probably fine" and confirm the published page after the push.

## Recipe (Git Bash, Windows Ruby)

```bash
G=$(mktemp -d); S=$(mktemp -d)
GEM_HOME="$G" GEM_PATH="$G" gem install 'jekyll:~>4.3' jekyll-remote-theme jekyll-seo-tag \
  jekyll-include-cache webrick csv base64 bigdecimal logger --no-document
GW=$(cygpath -m "$G"); SW=$(cygpath -m "$S"); J=$(ls "$G/gems" | grep '^jekyll-4')
( cd docs && GEM_HOME="$GW" GEM_PATH="$GW" ruby "$GW/gems/$J/exe/jekyll" build -s . -d "$SW/_site" )
```

The first three of these were failures hit on 2026-09-24 with Ruby 3.3:

- **Pass every path to Ruby in Windows form (`cygpath -m`).** Windows Ruby cannot read Git Bash's
  `/tmp/...` paths. It fails with `LoadError: No such file or directory -- /tmp/.../exe/jekyll`.
- **Run `exe/jekyll` through `ruby`, not `$G/bin/jekyll`.** The generated bin wrapper is a shell
  script that execs a `ruby` sitting beside it. There is none, so it exits 127.
- **Pin versions with `'gem:req'` syntax.** `gem install -v` refuses as soon as more than one gem is
  named: "Can't use --version with multiple gems".
- `webrick`, `csv`, `base64`, `bigdecimal` and `logger` were installed up front rather than after a
  failure. Newer Rubies no longer ship them as default gems, and Jekyll or its plugins require
  them. Which ones a given Ruby actually needs was not measured.
- `jekyll-seo-tag` and `jekyll-include-cache` are the gems just-the-docs' layouts call. With
  `remote_theme`, the theme's own gem dependencies are not installed for you, so add them by hand.

`remote_theme` downloads the theme from GitHub during the build, so the build needs network access.

## Viewing it

Build a second copy with `--baseurl ""` and serve that one. The real build's links all start with
`/<repo>/`, so they break under a plain static server:

```bash
( cd docs && GEM_HOME="$GW" GEM_PATH="$GW" ruby "$GW/gems/$J/exe/jekyll" build -s . -d "$SW/_local" --baseurl "" )
( cd "$S/_local" && nohup python -m http.server 8765 --bind 127.0.0.1 > "$S/http.log" 2>&1 & )
```

`python -m http.server` does not map `/pages/configuration` to `configuration.html` the way Pages
does. Request the `.html` URL, or you get a 404 page that screenshots as a plausible blank page.

For screenshots, headless Chrome needs no machine takeover:
`chrome --headless=new --user-data-dir=<temp> --window-size=1280,1400 --screenshot=<out.png> <url>`.
Chrome will not go narrower than roughly 500px (see `claude-in-chrome-probing.md`), so this cannot
show a phone layout.

Clean up afterwards. Find the server by its port (`netstat -ano | grep 127.0.0.1:8765`), kill it,
and delete the temp dirs by their literal paths. The Bash safety check refuses an `rm -rf` whose
target is a `$(...)` substitution.
