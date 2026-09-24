# Jekyll runs Liquid over page content, code spans included

Any `{{ … }}` or `{% … %}` in a Jekyll page is Liquid, wherever it sits in the markdown. Liquid runs
before kramdown, so a backtick code span or a fenced block protects nothing: by the time markdown
sees the text, Liquid has already evaluated it. An unknown variable renders as an empty string, so
the page builds cleanly and the text just goes missing.

Measured 2026-09-24 on a GitHub Pages site documenting a `{{kebab-case}}` placeholder feature. The
source said

```
optionally fills `{{kebab-case}}` placeholders (e.g. `{{tvdb-api-key}}`) with …
```

and the published page read *optionally fills `placeholders (e.g.`) with …*. Both variables
evaluated to nothing, and the leftover backticks paired up across the gap. Nothing failed, and the
README said the same thing correctly because github.com renders markdown without Liquid. The
fault sat unnoticed on the site until someone read the rendered sentence.

## Escaping it

Wrap the literal braces in `{% raw %}` … `{% endraw %}`. The tags can sit inline around the code
spans:

```
optionally fills {% raw %}`{{kebab-case}}` placeholders (e.g. `{{tvdb-api-key}}`){% endraw %} with …
```

Liquid consumes the tags and emits the text between them verbatim, and kramdown then renders the
spans as code.

**Do not use `render_with_liquid: false` on GitHub Pages.** It is a Jekyll 4.0 front-matter key.
Pages runs Jekyll 3.10 (`https://pages.github.com/versions.json`), where
`Convertible#render_with_liquid?` checks only whether the content contains a Liquid construct and
never reads the key. The page builds, and the braces vanish anyway.

## Finding the cases

Grep the site source for the delimiters. On GitHub Pages every hit is either deliberate Liquid or a
literal that renders wrong:

```bash
git grep -n -F '{{' -- docs ':!docs/plans'
git grep -n -F '{%' -- docs ':!docs/plans'
```

Verify with the same Liquid Pages runs (4.0.4). A throwaway gem dir is enough, and there is no
need for a full Jekyll build:

```bash
G=$(mktemp -d) && gem install liquid -v 4.0.4 --no-document -i "$G" >/dev/null
GEM_PATH="$G" ruby -e 'require "liquid"; print Liquid::Template.parse(File.read(ARGV[0]), error_mode: :strict).render({})' docs/index.md | grep -n placeholder
```

The same trap applies to includes, where an HTML comment protects nothing either. See the footer
section of `just-the-docs-customization.md`.
