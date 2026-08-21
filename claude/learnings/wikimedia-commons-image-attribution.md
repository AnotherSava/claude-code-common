# Pulling photographs and their credits out of Wikimedia

Companion to `wikimedia-poi-worth-sources.md`, which covers whether a place is worth
visiting. This covers showing a picture of it and crediting the picture correctly.
Measured across ~400 files behind Vancouver and Detroit POI datasets.

Two sources of a photograph for a subject that has a Wikidata item and/or a Wikipedia
article:

- **Wikidata `P18`** — a curated claim about the entity. Arrives as
  `http://commons.wikimedia.org/wiki/Special:FilePath/<percent-encoded name>`, over
  plain `http`, pointing at the **full-resolution original**.
- **`prop=pageimages`** — the article's lead image. Free if you already fetch
  `prop=extracts`: the two combine in one request, and the 20-title cap that `exintro`
  imposes does not apply to pageimages (a 25-title probe served images for all 25 while
  capping extracts at 20; the response's `continue` carried `"||pageimages"`, the
  completed-module list).

## Query file metadata at the article wiki, not at Commons

`en.wikipedia.org/w/api.php` resolves **both** Commons files and local uploads. Commons
resolves only its own, so it returns nothing for a local en.wikipedia file — and lead
images are occasionally local. One endpoint, one client, one retry policy.

### The trap: it flags every Commons file `missing` while returning full metadata

A Commons file queried at en.wikipedia comes back as:

```json
{ "title": "File:...", "missing": true, "known": true,
  "imagerepository": "shared", "imageinfo": [ { ...complete... } ] }
```

`missing` here means "no local page", not "no such file". Filtering on it first reported
106 of 108 files as absent; filtering on the **presence of `imageinfo`** resolved 365 of
365. The wrong test fails silently — you get images with no attribution, not an error.

```python
if not (info := page.get("imageinfo")):   # right
    continue
if page.get("missing"):                    # wrong: drops ~100% of Commons files
    continue
```

Note the asymmetry: for **article** titles `missing` is trustworthy. Same key, opposite
meaning, depending on the namespace.

### And its copy of shared metadata is sometimes incomplete

Even when `imageinfo` is complete, en.wikipedia's cached `extmetadata` for a *shared*
file is occasionally just `Categories` — no `Artist`, no `LicenseShortName`. Commons
reports all of it for the same file. Which file is affected is cache-dependent and moves
between runs, so it can't be treated as a fixed known loss.

Fix: after the main pass, re-ask **Commons** for anything that came back without a
licence and whose `descriptionurl` is on `commons.wikimedia.org` (a local upload's own
wiki is already the authority, so there is nothing to repair). Drop whatever is still
uncredited rather than displaying it — every genuinely free file names its licence,
public-domain ones included, so silence means the metadata never arrived.

## Never render the original

`P18` and `imageinfo`'s `url` both point at the source file. Two POIs in one dataset
shared a `P18` pointing at a **582 MB TIFF** no browser will draw; its 500 px thumbnail
is a 52 KB JPEG. Use `iiurlwidth=<n>` and take `thumburl`.

- **Widths round up to buckets**: 200→250, 320→330, 400/480/500→500, 640/800→960,
  1600→1920. Ask for a bucket value or the reported box won't match the bytes served.
- **`thumbwidth`/`thumbheight` describe the box you asked for, not the file you got.** A
  293×952 original at `iiurlwidth=500` reports `500×1625`. Derive aspect ratio from
  `width`/`height` (the original), never from the thumb fields.
- **`responsiveUrls["2"]` is not a safe 2× srcset.** When the original is narrower than
  2× the request it is tagged `thumbnail_unscaled` and points at the full original.
- A request wider than the original returns the original, unscaled.
- `thumburl` carries `?utm_source=…&utm_campaign=…&utm_content=thumbnail`. Analytics
  only — identical bytes come back without it.
- Thumbnails render fine for `.svg`, `.tif`, `.webp` and `.png`; the *original* URL does
  not. Median 500 px thumbnail weight ≈ 60–75 KB.

## `pilicense=free` is the default and must stay

`pilicense=any` looks like more coverage and is strictly worse: it swaps real
photographs for fair-use logos off the article wiki's non-free store. Little Caesars
Arena goes from a Commons CC BY-SA 4.0 photograph to `Little_Caesars_Arena_logo.svg`
(`imagerepository: local`, `LicenseShortName: Fair use`). With `free`, zero fair-use
files reached the results.

## `P18` beats the lead image, and both need a junk filter

PageImages returns the **first suitable image on the page**, which is not a claim about
the subject. Of 202 subjects holding both, the two disagreed for 87, and every clearly
wrong pick was the lead image: an aerial *map* for a park, a 2024 *logo* for a zoo, a
*logo* for a museum whose `P18` is a photograph of its building, and a neighbouring
tower for a named skyscraper.

A category filter catches most of it — reject when `mediatype != "BITMAP"`, or any
`extmetadata.Categories` entry (pipe-separated) matches
`\b(logos?|maps?|coats? of arms|flags?|seals?|diagrams?|floor ?plans?|icons?)\b`.
Measured: 19 of 354 lead images and 3 of 365 `P18` files, one of the latter a false
positive.

**The "Photographs of" exemption is load-bearing.** Commons files real photographs under
whatever is incidentally in frame, so a museum photo sits under "Photographs of flags of
<state>" and is rejected without it. Skip any category whose name starts with
`photographs of`.

Filter at parse time, not at the call site — rejecting a bad `P18` there is what lets
the lead image fall through and replace it, which is exactly the case where the two
sources compose well.

Residual after filtering: roughly 6% of accepted lead images show something *adjacent*
to the subject rather than the subject. No cheap rule sees that; the file is a perfectly
good photograph of the wrong thing.

## Credits: fetch, don't assume

The licences are not one licence. One city's ~200 files spanned CC BY-SA 3.0, public
domain, CC BY-SA 4.0, CC BY 2.0, CC BY-SA 2.0, Attribution, CC0 and CC BY 4.0, and most
carried `AttributionRequired`. A blanket "via Wikimedia Commons" is wrong for nearly all
of them.

```
iiprop=url|size|extmetadata|mediatype
iiextmetadatafilter=Artist|LicenseShortName|LicenseUrl|Categories
iiurlwidth=500&redirects=1&titles=<up to 50 File: titles>
```

50 titles resolve in one request (~93 KB of JSON), and `Categories` + `mediatype` ride
along free — which is what makes the junk filter cost nothing.

- **`Artist` is wiki-authored HTML** — `<a href=…>Name</a>`, `<p>Name\n</p>`,
  `Name at English Wikipedia<br>Later versions were uploaded by…`. Raw it is an
  injection vector; escaped it renders as visible tag soup. Reduce to text, and
  substitute a **space** for `<br>`/`</p>`/`</div>`/`</li>` before stripping tags or two
  names weld together. Then unescape entities. Median 12 chars, longest ~93.
- **`LicenseUrl` is absent for public-domain files** — there is no deed to link. Render
  the licence name as plain text there rather than requiring a URL.
- Take the file page from **`descriptionurl`**, never construct
  `commons.wikimedia.org/wiki/File:…` — it 404s for local uploads.
- `Artist` is genuinely missing for a small minority; "unknown author" is the honest
  fallback, and Commons often says exactly that itself.

## Title round-trips

- `P18` → file title: split on `Special:FilePath/`, percent-decode. `%2C` is real
  (`Fox%20Theatre%2C%20Detroit.jpg`). Feeding the raw path segment to the API matches
  nothing.
- `pageimage` → file title: it is a bare underscored name with **no namespace**
  (`Fox_Theatre,_Detroit.jpg`); prefix `File:` and swap underscores for spaces.
- **File titles need the same `normalized`/`redirects` join as article titles.** Commons
  redirects one file name onto another exactly as a wiki redirects articles, and a
  positional match attaches one subject's credit to another's photograph.
