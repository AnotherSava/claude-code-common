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
$content-width: 87.5rem; // ~1400px at 16px base
```

The default is ~66rem (~1056px). The value **must be in `rem`** — GitHub Pages uses sass 3.x which rejects mixed `px`/`rem` arithmetic. 87.5rem (~1400px) is a good middle ground for docs with wide code blocks or tables.

Do NOT edit `_sass/support/variables.scss` directly — it can break other dependencies.

### `$content-width` ≠ the `xl` breakpoint

`$content-width` drives exactly **one** rule — `.main { max-width }`, emitted inside `@media (min-width: 50rem)`. It does **not** touch the theme's responsive breakpoints. just-the-docs bakes a fixed xs/sm/md/lg/xl scale into the compiled CSS; the `xl` breakpoint is `87.5rem` (1400px) and appears ~20+ times as `@media (min-width: 87.5rem){…}` for utility classes (`.d-xl-*`, grid helpers). Those are **independent of `$content-width`** and won't change when you lower it — seeing them in the compiled CSS after a content-width change is expected, not leftover cruft. (It's a coincidence that the common 87.5rem content-width override equals the xl breakpoint.)

To verify a width change actually applied, grep the compiled `assets/css/just-the-docs-default.css` for the `.main{…max-width…}` rule, or measure `.main` in a browser — don't infer from the count of `87.5rem` strings.

### Compiled CSS is cached aggressively

`just-the-docs-default.css` is served with no content hash in its filename, so browsers hold the old copy after a Pages redeploy. A change confirmed live in the fetched CSS but "not showing" is almost always browser cache — hard-refresh (Ctrl+Shift+R).

## Suppressing the auto child-list (`has_toc`)

A page with `has_children: true` makes just-the-docs auto-render a "Table of contents" list of its child pages at the bottom of the page body. If the page *also* has a hand-written navigation block (e.g. a "Next steps" section that links the same children with descriptions), the two duplicate each other.

Set **`has_toc: false`** in the page's front matter to suppress the auto-generated child-list while keeping `has_children: true` (so the sidebar still nests the children). Prefer this when your manual list carries descriptions the bare auto-list lacks.

## Removing the footer attribution

just-the-docs renders "This site uses Just the Docs, a documentation theme for Jekyll." in the page footer. That text is the **default content of the theme's `_includes/footer_custom.html`** — not a config option.

To remove it, create an **empty** `_includes/footer_custom.html` in your own site. Jekyll resolves local `_includes/` before the remote theme (same precedence as the `_sass/` overrides above), so the empty file shadows the theme's default and the line disappears — the rest of the footer (search, "back to top") is untouched. To replace it with your own text (a copyright line, etc.) instead of removing it, put that markup in the same file.

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
