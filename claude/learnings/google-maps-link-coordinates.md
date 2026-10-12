# Getting a coordinate out of a Google Maps link

An app that wants an exact point from a person is going to be handed a Maps link, because that is what the Share
button produces and typing a latitude is nobody's habit. Whether the link contains the point depends on what was
shared, and the failure mode is the dangerous direction: the page a link opens carries a coordinate that looks
like the place and is the requesting computer.

Everything below was measured on 2026-10-11 against real links, from a server with no API key.

## What a short link expands to

`https://maps.app.goo.gl/<key>` is an HTTP redirect, so `curl -L` or a server-side `fetch` resolves it with no
browser. What it resolves *to* is the whole question:

| Shared thing | Expansion | Point present |
|---|---|---|
| A **pin** (press and hold a spot in the app) | `?q=<lat>,<lng>&entry=gps&…` | Yes — a bare pair, with tracking parameters piled after it |
| A **business or saved place** | `?q=<its name and street address>&ftid=<hex>:<hex>` | No — the place is named twice and located nowhere |

So a short link is worth following, and following it is not sufficient. Read the expansion rather than treating
the redirect's success as the answer.

## The number on that page is the requester's own location

The HTML served for a `?q=<address>&ftid=…` URL contains exactly one coordinate, and it is the map camera:

```
window.APP_INITIALIZATION_STATE=[[[20819.797,<lng>,<lat>],[0,0,0],[1024,768],13.1], …
<meta content="https://maps.google.com/maps/api/staticmap?center=<lat>%2C<lng>&zoom=14&…"
```

The decisive test is to ask for something else entirely. A Sydney Opera House query, a query for a station in
another country, and a bare `https://www.google.com/maps` all return **the same** pair — it is derived from the
requesting IP, at ~20.8 km altitude and `zoom=14`. On the measured run it sat 2.3 km from the address in the
URL, which is close enough to pass a glance and wrong enough to send somebody to the wrong block.

Scraping it is therefore not a degraded answer, it is the server's own location stored as the user's place.
Nothing should read a coordinate off that page.

Three lookups that all answer with the same shell, so none of them is a way round this:

- `https://maps.google.com/?cid=<decimal of the ftid's second hex half>`
- `https://www.google.com/maps?ftid=0x…:0x…`
- `https://www.google.com/maps/place/?q=place_id:<id>`

## A browser does resolve it, and `--dump-dom` cannot see the answer

Load the link in a real browser and the place resolves client-side, after which the address bar reads:

```
/maps/place/<name>/@<lat>,<lng>,17z/data=…!3d<lat>!4d<lng>…
```

That URL carries the point twice and is the thing to copy by hand. Two mechanics matter when automating it:

- **`chrome --headless --dump-dom` is the wrong instrument.** The DOM it prints still holds only the IP camera,
  because the real coordinate arrives in a later XHR and the URL is rewritten with `history.pushState` — a DOM
  dump cannot report a URL. Measured: `--dump-dom` with `--virtual-time-budget=20000` gave a page whose
  `<title>` had resolved to the place's name while every coordinate in it was still the camera's.
- **CDP reads it in one line.** `puppeteer-core` against the Chrome already installed needs no browser
  download: `npm install --no-save puppeteer-core`, launch with `executablePath` pointing at the app binary,
  `page.goto(link, {waitUntil: 'networkidle2'})`, poll `page.url()` until it matches `@-?\d+\.\d+,-?\d+\.\d+`.

Weigh that against what it costs in production: a headless browser inside a container is a few hundred megabytes
of image and a second runtime to patch, so for a one-paste-a-month feature the honest design is to refuse the
link and tell the person what to copy.

## Which pair in a URL is the place

A `/maps/place/` URL carries two, and they are different facts:

- `!3d<lat>!4d<lng>` inside the `data=` payload is **the place's own point**.
- `@<lat>,<lng>,<zoom>z` is **the viewport centre** the link was shared at.

They agree on a link copied while looking at the pin and disagree on a shared one, where `@` is wherever the map
happened to be sitting. Prefer `!3d/!4d`, fall back to `@`. Also readable, and worth accepting: `?query=`,
`?q=`, `?ll=` and `?center=` holding a pair, and a `geo:` URI.

## Parsing what a person pastes

Four shapes cover what is actually in a clipboard: a decimal pair, a degrees-minutes-seconds reading
(`33°51'24.3"S 151°12'55.1"E`, which is what the pin's own panel shows), a long `/maps/place/` URL, and a short
link. Two rules are worth having tests for:

- **A DMS pair needs one of N/S and one of E/W.** Without the letters there is no stated order, and guessing
  puts the pin in the wrong hemisphere while looking entirely plausible. Accept the letter on either side —
  `33°51'24"S` and `S 33°51'24"` are both written — and match `′ ″` as well as `' "`, since a copy out of a
  rendered page brings the typographic forms.
- **Check both halves of a pair against their own ranges** rather than clamping. A pair pasted in the other
  order fails on the latitude for most of the world, so the refusal can say "if the pair is the other way
  round, swap it" — but a pair whose both halves are in range is undetectable, which is the argument for
  showing the stored point back as a link the person can click.

## Telling someone how to get one

The gesture differs per device and the instruction has to say both, because a phone has no right-click:

- **Computer:** right-click the exact spot, click the numbers at the top of the menu.
- **Phone:** press and hold the spot until a pin drops, then read or share that — a pin carries its coordinate
  where a business listing carries only its address.

## Related

- `geopy-nominatim-batch-geocoding.md` is the other direction — an address to a point, with a geocoder. Reach
  for it only where inventing a coordinate is acceptable; everything above exists because a guessed point is
  indistinguishable from a checked one once stored.
