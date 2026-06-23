# Aligning text columns in OS-native title tooltips

The native `title=""` tooltip (rendered by the browser/WebView chrome, not the page) is the only way to show a multi-line hover bubble that can exceed the host window's bounds — useful for a small/frameless widget. But it has hard constraints:

- It renders the **OS UI font, proportional** (Segoe UI on Windows), and **cannot be styled** — no CSS, no monospace, no font-family control.
- It **does** preserve `\n` (multi-line) and **leading whitespace** (indentation). So multi-column / hanging-indent layouts are possible — but only if you pad with the right-width blanks.

The trap: a column padded with regular spaces won't line up under digits, because a space is narrower than a digit in a proportional font. `"18:56" + "    "` is wider than 9 regular spaces, so a wrapped continuation line indented with 9 spaces drifts left of the prompt text.

## Fixed-width blanks for known glyph classes

Most UI fonts have **tabular figures** (all digits share one advance) plus standardized spacing glyphs sized to them:

- **Figure space U+2007** ≈ one tabular digit width → use for each digit position.
- **Punctuation space U+2008** ≈ a period/colon width → use for `:`.
- Regular space U+0020 for literal spaces.

So to blank out an `HH:MM` prefix for a hanging indent, map char-by-char: digit → ` `, `:` → ` `, space → `†`… i.e. build a same-width blank glyph-by-glyph. In Segoe UI these line up under `HH:MM` precisely.

```ts
// Hanging indent the same rendered width as `prefix`.
function blankLike(prefix: string): string {
  let out = ''
  for (const ch of prefix) {
    if (ch >= '0' && ch <= '9') out += ' '        // figure space ≈ digit
    else if (ch === ':') out += ' '               // punctuation space ≈ colon
    else out += ' '
  }
  return out
}
```

## Arbitrary glyphs: measure at runtime, pad with sub-space blanks

There is **no** standard space matching an arbitrary glyph (e.g. a `▸` marker). Guessing "≈ 2 spaces" fails — proportional widths aren't integer multiples of a space. The robust fix is to **measure** with a canvas in the same font and assemble padding from a palette of progressively narrower spaces.

- Ratios are **size-independent**, so any measurement px works: `ctx.font = '40px "Segoe UI"'`.
- Palette, widest→narrowest, for sub-space precision: regular ` `, figure ` `, thin **U+2009**, hair **U+200A**.
- Greedily fill the target width (never overshoot; residual < one hair space = sub-pixel at tooltip size).
- To center a glyph in a fixed gap, split the leftover width into left/right pads.

```ts
const ctx = document.createElement('canvas').getContext('2d')!
ctx.font = '40px "Segoe UI", system-ui, sans-serif'
const w = (s: string) => ctx.measureText(s).width
const palette = [[' ', w(' ')], [' ', w(' ')], [' ', w(' ')], [' ', w(' ')]]
  .filter(([, x]) => x > 0).sort((a, b) => b[1] - a[1])
const pad = (target: number) => {           // approximate `target` px with blanks
  let s = '', rem = target
  for (const [ch, cw] of palette) while (rem >= cw) { s += ch; rem -= cw }
  return s
}
const gapPx = 4 * w(' '), arrow = w('▸')
const left = pad((gapPx - arrow) / 2)
const marker = left + '▸' + pad(gapPx - arrow - w(left))  // ▸ centered in a 4-space-wide gap
```

Then the hanging-indent map needs the matching blank for that glyph: `▸ → pad(arrow)`, and any palette spaces in the padding pass through unchanged.

## Caveats

- The canvas must measure the **same font the tooltip renders**. On Windows the tooltip is Segoe UI and canvas uses the same DirectWrite engine, so it's pixel-accurate. Cross-platform the OS tooltip font differs (macOS system font), so measurement is only approximate there.
- Figure/thin/hair spaces are length-1 JS chars, so they don't disturb character-count wrap math — but they're invisible in editors. Verify file bytes with Python `ascii(line)`; many edit tools also silently normalize between a `\uXXXX` escape and the literal char.
- For **guaranteed** pixel-perfect alignment on all platforms, render a custom in-app tooltip (monospace + CSS hanging indent via `text-indent`/`padding`). The trade-off: a DOM tooltip is clipped to the window, losing the native tooltip's ability to overflow a small/frameless widget.

Worked example: `SessionItem.svelte` in the tauri-dashboard repo (recent-prompts hover tooltip: `HH:MM` column, hanging-indented wrapped prompts, a centered `▸` marking the current task).
