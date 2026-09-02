# just-the-docs customization

## SCSS overrides

Two override files, loaded at different stages:

| File | When loaded | Use for |
|---|---|---|
| `_sass/custom/setup.scss` | After theme variables/functions, before CSS classes | Variable overrides (`$content-width`, `$nav-width`, etc.) |
| `_sass/custom/custom.scss` | After all CSS classes are emitted | Class-level overrides (`.main { ... }`) |

Both work with `remote_theme: just-the-docs/just-the-docs` — Jekyll checks local `_sass/` before the theme's.

## Content width

The main content area width is controlled by the `$content-width` variable, applied to `.main` at medium+ breakpoints. There is **no `.main-content` class** — using that selector is a silent no-op.

```scss
// _sass/custom/setup.scss
$content-width: 68.75rem; // 1100px at a 16px base — but read the breakpoint section below first
```

The default is **`50rem` (800px)** — verified against `_sass/support/_variables.scss` on `main`, which is what `remote_theme` pulls. The value **must be in `rem`** — GitHub Pages uses sass 3.x which rejects mixed `px`/`rem` arithmetic.

Do NOT edit `_sass/support/variables.scss` directly — it can break other dependencies.

### Raising `$content-width` also moves the sidebar breakpoint

It is not a width knob. Two of the theme's five breakpoints are *derived* from it:

```scss
$content-width: 50rem !default;
$media-queries: ( xs: 20rem, sm: 31.25rem, md: $content-width, lg: $content-width + $nav-width, xl: 87.5rem );
```

`.side-bar` becomes the fixed left rail at `mq(md)`, so `md` is the window width at which the site stops rendering as a mobile header. Raising `$content-width` raises it with them:

| `$content-width` | sidebar appears at (`md`) | centred-gutter layout at (`lg`) |
|---|---|---|
| `50rem` (default) | 800px | 1064px |
| `68.75rem` | 1100px | 1364px |
| `87.5rem` (the common override) | **1400px** | 1664px |

So the popular 87.5rem override silently gives a 1366px laptop the mobile layout. Only `xl` (a literal 87.5rem, driving `.d-xl-*` utility classes) is independent — it does not move when you change the variable, and seeing `@media (min-width: 87.5rem)` in the compiled CSS afterwards is expected rather than leftover cruft.

**The two cannot be decoupled** by overriding `.main { max-width }` in `custom/custom.scss` and leaving the variable alone. At `lg`, `.side-bar` and `.side-bar + .main`'s `margin-left` are both `calc((100% - #{$nav-width + $content-width}) / 2 + #{$nav-width})` — the layout centres a `nav + content` block of exactly that total. A `.main` wider than `$content-width` overflows the right edge on any window narrower than roughly `2 × main − nav`; with `$content-width: 50rem` and `.main` forced to 68.75rem that is anything under ~1500px. The variable is the only correct lever, and moving the breakpoints with it is the design, not a bug.

Decide accordingly: a wide table is usually better served by letting the theme's `.table-wrapper` scroll than by pushing every reader under 1400px into the mobile layout.

To verify a width change actually applied, grep the compiled `assets/css/just-the-docs-default.css` for the `.main{…max-width…}` rule, or measure `.main` in a browser — don't infer from the count of `87.5rem` strings.

### Compiled CSS is cached aggressively

`just-the-docs-default.css` is served with no content hash in its filename, so browsers hold the old copy after a Pages redeploy. A change confirmed live in the fetched CSS but "not showing" is almost always browser cache — hard-refresh (Ctrl+Shift+R).

## Suppressing the auto child-list (`has_toc`)

A page with `has_children: true` makes just-the-docs auto-render a "Table of contents" list of its child pages at the bottom of the page body. If the page *also* has a hand-written navigation block (e.g. a "Next steps" section that links the same children with descriptions), the two duplicate each other.

Set **`has_toc: false`** in the page's front matter to suppress the auto-generated child-list while keeping `has_children: true` (so the sidebar still nests the children). Prefer this when your manual list carries descriptions the bare auto-list lacks.

## Removing the footer attribution

just-the-docs renders "This site uses Just the Docs, a documentation theme for Jekyll." Removing it is not a config option, and the obvious guess — shadowing `_includes/footer_custom.html` with an empty file — is wrong three times over. Verified against the theme on `main` and against a live Pages deploy.

**The include is `nav_footer_custom.html`, not `footer_custom.html`.** The latter is an unrelated hook that renders `site.footer_content` if you set it; shadowing it suppresses that feature and leaves the attribution untouched. The attribution is the *else-branch* of a test in two theme partials, both reading the same include:

- `_includes/components/sidebar.html` — desktop, inside `<div class="d-md-block d-none site-footer">`
- `_includes/components/footer.html` — mobile, inside `<div class="d-md-none mt-4 fs-2">`

**An empty file does the opposite of what you want.** The guard is `if nav_footer_custom != ""`, and the theme's own copy of the file is 0 bytes — so empty takes the else-branch and prints the attribution. Your override must be **non-empty and render nothing**. An HTML comment satisfies both. (Note this is inverted from `footer_custom.html`, where empty genuinely means "render nothing" — which is exactly why the wrong guess feels right.)

**The payload is parsed as Liquid, comment or not.** An include's contents go through the Liquid parser before any HTML is considered, so a `{%` sequence inside an HTML comment is a real tag. Writing the theme's own guard verbatim into an explanatory comment produced `Liquid syntax error (components/sidebar.html line 8): 'if' tag was never closed` and failed the Pages build outright. Keep `{%` and `{{` out of the file entirely.

Two verification traps, both of which will convince you the fix failed when it worked:

- **Don't quote the attribution sentence in your comment.** `curl … | grep 'This site uses Just the Docs'` then matches your own suppressor. Strip comments before grepping, or keep the phrase out of the file.
- **A failed Pages build serves the previous deploy.** The legacy `/pages/builds/latest` API can sit on `building` while the Actions run has already failed, so the live page keeps showing the old footer and looks like the change did nothing. Check `gh run list` for the `pages build and deployment` run's conclusion before drawing any conclusion from the served HTML.

Works identically under `remote_theme: just-the-docs/just-the-docs`.

## Mermaid diagrams

just-the-docs has **built-in mermaid support** — no plugin needed. Enable it in `_config.yml`:

```yaml
mermaid:
  version: "11.4.1"   # loaded from jsDelivr CDN; pin a real published version
```

Any ` ```mermaid ` fenced block then renders client-side, styled to the theme. Prefer mermaid over ASCII box-art: ASCII box-drawing diagrams render as flat monospace and look poor in the theme.

Pick the representation by diagram type:

- **Flowcharts / data-flow diagrams** → a ` ```mermaid ` `flowchart` block.
- **File trees / directory layouts** → a **nested Markdown bullet list** (file/dir names as inline `code`, descriptions after `—`). The theme styles nested lists with indent guides; a list reads better than a tree here and needs no mermaid. Collapse single-child dirs onto one line (`adapters/claude.rs`).

Mermaid label gotchas (these break rendering or render wrong):

- Quote any edge/node label with special chars: `-->|"#[tauri::command]"|`, `-->|"a -> b"|`.
- Inside node labels, use `&lt;`/`&gt;` for angle brackets and `<br/>` for line breaks: `AS[("AppState<br/>Mutex&lt;Vec&lt;T&gt;&gt;")]`.
- Validate the diagram parses (e.g. the claude-mermaid plugin's `mermaid_preview`) before committing — a syntax error renders as a broken diagram on the live site, not a build failure.
