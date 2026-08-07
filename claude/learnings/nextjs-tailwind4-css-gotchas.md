# Next.js 16 (Turbopack) + Tailwind v4 CSS gotchas

Non-obvious CSS behaviours that cost real iteration in a Next.js 16 (App Router, Turbopack dev) + Tailwind v4 app. They all present as "the class is there but has no effect."

## Turbopack serves stale CSS after adding new utilities / editing globals rules

When you add a Tailwind **arbitrary** utility (`-ml-[11px]`, `px-[18px]`, `bg-[rgba(...)]`), add a new hand-written rule in `globals.css`, **or modify an existing rule/selector**, Turbopack's dev server can keep serving a compiled CSS chunk from an earlier compile. The class is present on the element in the DOM, but the served stylesheet has the old rule (or omits the new one), so it does nothing. Plain HMR and even a normal dev-server restart may not regenerate it (the persistent `.next` cache holds the old compile).

Editing an *existing* rule is affected too, not just additions: e.g. adding a selector to one rule's list can land while a *selector change on a neighbouring rule in the same edit* does not — the served CSS shows the new stroke rule but keeps the old `.wn-gear:hover` transform selector instead of the edited `.wn-gear:not(.wn-gear-on):hover`.

**Symptom:** a computed style is wrong in a way that matches "the rule never applied" — e.g. `opacity: 1` where you wrote `opacity: 0`, or a nav link computing to the body colour. Iterating `document.styleSheets` (recursing into `@layer` blocks) for the selector finds the **old** rule text, or nothing, while *other* hand-written rules from the same file that were added in an *earlier* compile ARE present. That split — old rules present, newest ones missing/unedited — is the tell.

**Fix:** stop the dev server, `rm -rf .next` (the *whole* dir), restart. Forces a clean CSS regen. Partial clears do **not** work — the dev cache lives under `.next/dev/` (`.next/dev/cache/turbopack/`), so removing `.next/cache`, `.next/static`, or `.next/server` leaves the stale compile intact.

**Sidestep it for layout-critical values:** use inline `style={{ marginLeft: -11 }}` instead of `-ml-[11px]`. Inline styles are part of the RSC/HTML payload and never depend on the CSS bundle's freshness, so they can't be broken by a stale rebuild. Reserve this for a handful of alignment-critical properties, not everything.

**Verify from the browser, don't eyeball:** compare `getComputedStyle(el)` (and `getBoundingClientRect()` deltas) against intent; to confirm a rule actually made it into the bundle, fetch the served chunk and grep it:

```bash
css=$(curl -s http://localhost:PORT/ | grep -oE '/_next/static/[^"?]+\.css' | head -1)
curl -s "http://localhost:PORT$css" | grep -o 'your-class' | wc -l   # 0 = stale bundle
```

## Unlayered `a { color: inherit }` overrides Tailwind's text-color utilities

A reset written directly in `globals.css` **outside any `@layer`** — e.g.

```css
a { color: inherit; text-decoration: none; }
```

is *unlayered*, and in the CSS cascade **unlayered rules beat every `@layer` rule regardless of specificity**. Tailwind v4 emits its utilities into `@layer utilities`, so this `a` rule wins over `text-white`, `text-[var(--color-muted)]`, etc. on **every** `<a>`. Result: `<a className="text-[var(--color-muted)]">` renders the *inherited* body colour, not muted — silently, on every link in the app.

**Symptom:** nav/footer links (or any `<a>` with an explicit `text-*` class) all compute to the same body text colour; the `text-*` class appears in `className` but `getComputedStyle(a).color` ignores it.

**Fix:** wrap the reset in the base layer so utilities cascade over it:

```css
@layer base {
  a { color: inherit; text-decoration: none; }
}
```

Links with no colour class still inherit; links with one now honour it. (Same reasoning applies to any element reset you write unlayered — put resets in `@layer base`.)

## Some arbitrary utilities never generate — even after `rm -rf .next`

Distinct from the stale-cache case above: a small set of arbitrary utilities refuse to appear in the bundle *at all*, no matter how many clean rebuilds you do. Two reproduced cases:

- **A hover-variant of a `[var(--theme-color)]` background:** `hover:bg-[var(--color-border)]` (where `--color-border` is a `@theme` colour) was verified absent from every stylesheet after **two full `.next` clears + restarts** — while `group-hover:text-[var(--color-text)]` on the *same element* generated fine, and plain `bg-[#c4c4cc]` in a quoted className works. So it's specific to certain arbitrary-value + variant combinations (the arbitrary `bg-[var(--color-border)]` likely competing with the theme-generated `bg-border` utility). Clearing `.next` again does nothing.
- **A class token immediately before `${` in a template literal** (no separating space): `` `text-pretty text-[12px] text-[#77777f]${cond ? " …" : ""}` `` — Tailwind's scanner reads the raw source text and the `]${` boundary breaks token extraction, so `text-[#77777f]` is never emitted, while the identical class in a plain quoted string (`"… text-[#c4c4cc]"`) works. Keep a **space before `${`**: `` `… text-[#77777f] ${cond ? "…" : ""}` ``.

**Fix when a utility stubbornly won't generate:** stop fighting the scanner — use a **named class in `globals.css`** (`.wn-dl:hover { … }`), the **semantic `@theme` utility** (`bg-border` instead of `bg-[var(--color-border)]`), or an **inline `style`** for the resting bits. Named hand-written rules always emit (subject only to the stale-cache clear above); the design reference's own hover affordances (`.wn-icobtn`, `.wn-dllink`) are done exactly this way.

**Confirm it's really missing** (not just stale) before clearing `.next` yet again: iterate `document.styleSheets` for a rule whose `selectorText` matches the element (or contains the escaped class) — an empty result after a clean rebuild means the utility genuinely wasn't emitted, so switch approaches instead.

## Preflight resets `button, input, select, optgroup, textarea` — but NOT `fieldset`

Tailwind v4's preflight does not touch `fieldset`, so a `<fieldset>` used purely as a grouping wrapper arrives with the browser's UA defaults intact: a `2px groove` border, `~0.35em 0.75em 0.625em` padding, `2px` inline margin, and `min-inline-size: min-content`. The last one is the nastiest — it can stop the element shrinking inside a flex/grid parent.

This is worth knowing because `<fieldset disabled>` is the *right* tool for "disable this whole block of controls" (it disables every descendant natively, including buttons, so a control added later can't be forgotten), and reaching for it is where you meet the missing reset.

**Verify rather than assume** — grep the served bundle for the element name:

```bash
css=$(curl -s http://localhost:PORT/ | grep -oE '/_next/static/[^"?]+\.css' | head -1)
curl -s "http://localhost:PORT$css" | grep -c 'fieldset'      # 0 = preflight doesn't reset it
curl -s "http://localhost:PORT$css" | grep -o 'button, input[^{]*{'   # what it DOES reset
```

**Fix:** clear the defaults explicitly on the element:

```tsx
<fieldset disabled={!enabled} className="mx-0 grid min-w-0 grid-cols-1 gap-3 border-0 p-0 disabled:opacity-45">
```

`disabled:opacity-45` works on the fieldset itself — a disabled fieldset matches `:disabled`, so the variant applies to the container, not just its children.

## Container queries are core in v4 (no plugin)

`@container` + `@sm:`/`@2xl:`… ship in Tailwind v4 itself. Reach for them when a component renders at more than one width — e.g. a form that appears both full-width and in a half-width column: viewport breakpoints (`sm:grid-cols-2`) can't tell those apart and will pair fields up inside a narrow column.

```tsx
<div className="@container">
  <fieldset className="grid grid-cols-1 gap-3 @2xl:grid-cols-2">…</fieldset>
</div>
```

Generated as `.@container { container-type: inline-size }` and `@container (min-width: 42rem) { .\@2xl\:grid-cols-2 { … } }`. Both are subject to the stale-bundle problem at the top of this file — a first check showed `container-type` present while the `@2xl:` rule was missing entirely, and `rm -rf .next` + restart emitted it.
