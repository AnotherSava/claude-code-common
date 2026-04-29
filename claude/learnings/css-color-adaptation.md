# CSS Color Adaptation

Modern Chromium-only techniques for adapting arbitrary input colors (theme colors, server-supplied hexes, BGA player colors) to a UI's contrast requirements without JavaScript color math.

## Lightness clamp via OKLCH relative color syntax

When a CSS custom property holds a user/server-supplied color, clamp lightness to a readable band while preserving hue and chroma:

```css
.label {
  color: oklch(from var(--player-color, #ccc) clamp(0.65, l, 0.85) c h);
}
```

How specific palette inputs land:

- Pure black `#000000` (L=0) → L=0.65, becomes medium gray
- Pure blue `#0000ff` (L≈0.45) → L=0.65, becomes readable on dark background
- Pure white `#ffffff` (L=1) → L=0.85, drops below body-text white so it's distinguishable
- Already-bright colors (yellow, cyan, pink, orange) → unchanged (already in band)

The `from` keyword takes any valid CSS color and exposes channels (`l`, `c`, `h` for OKLCH; `r`, `g`, `b` for RGB; `s`, `l` for HSL; etc.) for use in the new color expression. The fallback inside `var(--name, fallback)` works inside `from`, so the rule still produces a valid color when the custom property is unset.

Browser support: Chrome 119+ (Oct 2023), Safari 16.4+, Firefox 128+. Safe in any Manifest V3 Chrome extension.

## Low-alpha tint from a hex color

`color-mix(in srgb, ...)` produces a transparent tint of any input color, useful for "selected row" or "owner-indicator" backgrounds:

```css
.row.is-mine {
  background: color-mix(in srgb, var(--player-color) 12%, transparent);
}
```

The 12% picks a subtle background tint; tune per design (10–20% is typical for affordances). Mixing with `transparent` (rather than the parent background color) produces an alpha-compositing-friendly result that looks correct over any underlying background.

`color-mix` is also useful for derived state colors:

```css
.button:hover {
  background: color-mix(in oklch, var(--accent), white 15%);
}
```

## Why OKLCH over HSL

HSL lightness is perceptually uneven — pure yellow at L=50% looks much brighter than pure blue at L=50%. OKLCH is perceptually uniform, so a single lightness clamp produces visually consistent contrast across hues. When you're treating multiple unrelated input colors with the same rule, this matters.

For tints that mix one color into a neutral, `color-mix(in srgb, …)` is fine — the perceptual difference is small at low alphas. For computing accent-of-accent colors or readable-on-bg variants, prefer `oklch` everywhere.

## Pattern: inline style supplies the color, CSS supplies the treatment

The cleanest way to thread server-supplied colors into CSS is inline `style="--name: #hex"` on a wrapper element, with the CSS rule referencing `var(--name)`:

```html
<tr style="--player-color: #0000ff" class="row is-mine">…</tr>
```

```css
.row { color: oklch(from var(--player-color) clamp(0.65, l, 0.85) c h); }
.row.is-mine { background: color-mix(in srgb, var(--player-color) 12%, transparent); }
```

This keeps the palette fully data-driven (no JS color math, no per-color CSS classes to maintain) while letting CSS rules do the contrast/affordance treatments. Descendants inherit the custom property automatically.
