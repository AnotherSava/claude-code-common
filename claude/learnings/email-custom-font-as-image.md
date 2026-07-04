# Rendering a custom-font wordmark for HTML email

Email clients can't be trusted with web fonts. Apple Mail / iOS Mail honour `@font-face` and `<link>` webfonts, but **Gmail (web + apps) and Outlook strip them** and fall back to a system font. So a header/logo that must match a site's brand typeface will look wrong in a large share of opens if you rely on CSS fonts.

The robust fix: **render the wordmark to a raster image** and embed it, so every client shows identical pixels. Alt text covers image-blocking clients.

## Rendering custom-font text → PNG headlessly with `sharp`

`sharp` (libvips) has a `text` input that rasterises text via **Pango**, and it accepts an explicit **font file** — so no system font install / fontconfig setup is needed:

```js
import sharp from "sharp";

// Wordmark in a specific TTF, coloured + weighted via Pango markup. dpi 72 makes the markup
// point-size == pixels, so "Family 31" renders at ~31px. rgba:true → transparent background.
const text = await sharp({
  text: {
    text: `<span foreground="#17150f" weight="600">Acme Print Co.</span>`,
    font: "Hanken Grotesk 31",
    fontfile: "./HankenGrotesk.ttf", // variable or static TTF; downloaded from the google/fonts repo
    rgba: true,
    dpi: 72,
  },
}).png().toBuffer();

// Any vector mark (SVG paths, no font) rasterises normally and composites alongside:
const mark = await sharp(Buffer.from(`<svg ...>…</svg>`)).png().toBuffer();
const logo = await sharp({ create: { width: W, height: H, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 0 } } })
  .composite([{ input: mark, left: 0, top: 0 }, { input: text, left: markW + gap, top: 0 }])
  .png().toBuffer();
```

Notes:
- Render at **2–3× the display size** for crispness on retina; display it at `width`/`height` = the 1× dims.
- Pango markup: `foreground="#hex"` colours it, `weight="600"` selects the weight (works with variable-font TTFs via HarfBuzz). Setting `font-feature-settings`/tabular figures isn't relevant for a wordmark.

## Embedding in the email

Attach the PNG **CID-inline** (not a remote URL — remote images are blocked by default in many clients, and a `localhost` URL won't resolve for the recipient). With react-email:

```jsx
<Img src="cid:logo" width={W} height={H} alt="Acme Print Co." style={{ display: "block" }} />
```
…and attach `{ filename: "logo.png", content: pngBuffer, contentId: "logo" }`. To avoid runtime file IO / bundling issues in a standalone build, generate the PNG once (throwaway script) and commit it as a `base64` constant the mailer imports.
