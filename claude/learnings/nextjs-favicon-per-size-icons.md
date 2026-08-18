# Next.js favicons render blurry on HiDPI tabs — declare per-size icons

## Symptom
The browser-tab favicon looks soft/blurry on a scaled display (Windows 125%/150%, any HiDPI), even though `app/favicon.ico` already contains the right sizes.

## Root cause: frame *selection*, not a missing size
Next's file-convention `app/favicon.ico` emits a single link whose `sizes` is the **largest** frame it detects:

```html
<link rel="icon" href="/favicon.ico" sizes="48x48" type="image/x-icon"/>
```

(The docs claim `sizes="any"`, but a multi-size `.ico` gets tagged with its largest frame.) A tab at 150% scaling renders the favicon at **24 device px** (16 CSS px × 1.5). Chrome, told the icon is 48×48, **downscales the 48 frame to 24** with a smooth filter instead of decoding the `.ico` and using its native 24px frame — thin strokes smear. Render both to confirm: native-24 is crisp, 48→24 is soft and matches the bad tab.

Device-px per Windows scale: **100%→16, 125%→20, 150%→24, 175%→28, 200%→32**. Measure the real size by cropping a tab screenshot — the favicon's bbox in the (1:1) screenshot IS its device-pixel size (e.g. exactly 24×24 ⇒ 150%).

## Fix: declare per-size icons so the browser matches the exact size

### A. Numbered file convention (sizes auto-detected)
Drop `app/icon0.png`, `app/icon1.png`, … at 16/24/32/48. Next reads each file's real dimensions and emits `<link rel="icon" sizes="NxN">` per file; `favicon.ico` stays the fallback.
- **Matcher is `icon\d?(-\w{6})?\.(png|…)`** (`next/dist/lib/metadata/is-metadata-route.js`): `icon` + one **optional single digit** + an optional internal 6-char content-hash. So only `icon.png` and `icon0.png`–`icon9.png` work. **`icon-16.png` is NOT recognized** (the `-16` matches neither the single digit nor the 6-char hash). The number is just ordering — the size comes from the pixels. Max ~10 numbered icons.

### B. metadata.icons with named public files (self-documenting)
```ts
// app/layout.tsx
export const metadata: Metadata = {
  icons: {
    icon: [
      { url: "/icons/icon-16.png", sizes: "16x16", type: "image/png" },
      { url: "/icons/icon-24.png", sizes: "24x24", type: "image/png" },
      { url: "/icons/icon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/icons/icon-48.png", sizes: "48x48", type: "image/png" },
    ],
    apple: { url: "/apple-icon.png", sizes: "180x180", type: "image/png" },
  },
};
```
Files live in `public/icons/`. `app/favicon.ico` still auto-injects as the fallback and coexists (no duplicate).
- **Gotcha: setting `metadata.icons` SUPPRESSES the file-convention `apple-icon.png` auto-injection** (it keeps `favicon.ico` but drops apple). If you have `app/apple-icon.png`, its `<link rel="apple-touch-icon">` silently disappears — you must add `apple:` to `metadata.icons`, pointing at a `public/` file (move `app/apple-icon.png` → `public/`).

Approach A keeps Next's content-hash cache-busting; B's public URLs don't hash (bump `?v=` manually on change). Fractional DPIs you don't declare a native frame for (20px@125%, 28px@175%) still resample — add those sizes if you need them crisp.

## Verify
```bash
curl -s http://localhost:3000/ | grep -oE '<link[^>]*rel="(icon|apple-touch-icon)"[^>]*>'
```
Expect one `<link>` per declared size + the apple link. Chrome caches favicons hard — **close/reopen the tab or use Incognito** to see changes; Ctrl+Shift+R usually isn't enough.

## Hand-rolling a multi-size .ico (no ImageMagick / png-to-ico dependency)
`sharp` can rasterize SVG→PNG but can't write `.ico`. The container is trivial: 6-byte ICONDIR (reserved=0, type=1, count) + one 16-byte ICONDIRENTRY per image (width/height byte — 0 means 256; planes=1; bitcount=32; byte-length; offset) + the concatenated PNG blobs. Embedding PNG frames (rather than BMP) is Vista+ and universal in modern browsers. On Windows, `convert` on PATH is the **filesystem** tool (`C:\Windows\System32\convert.exe`), NOT ImageMagick — don't reach for it.
