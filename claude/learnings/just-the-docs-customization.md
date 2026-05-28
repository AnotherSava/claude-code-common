# just-the-docs SCSS customization

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
