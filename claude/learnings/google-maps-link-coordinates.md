# Getting a coordinate out of a Google Maps link

An app that wants an exact point from a person is going to be handed a Maps link, because that is what the Share
button produces and typing a latitude is nobody's habit. Whether the link contains the point depends on what was
shared, and the failure mode is the dangerous direction: the page a link opens carries a coordinate that looks
like the place and is the requesting computer.

Everything below was measured against real links, from a server with no API key — on 2026-10-11 unless a
paragraph gives its own date.

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

That includes reading the page *through a URL parser*. A fallback that pulls every Maps URL out of the HTML and
hands each to the same reader a pasted link goes through meets the `staticmap?center=` preview first — it sits
ahead of the place's own URLs — and a reader that accepts `?center=` stores the camera. Measured 2026-10-14: a
hotel's page answered with a point in another country, where the server sat. From a fetched page, take only
what a URL states about its place — `!3d/!4d`, a `!20s` plus code, a pair written into the `/maps/place/` path
— and never a query key or an `@`.

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

## A pasted link often has no scheme, and `new URL` needs one

Browsers hide `https://` in the address bar and a link retyped off a screen never had it, so
`google.com/maps/place/40.758000,-73.985500` is what a person actually holds — and it is not a URL to
`new URL`, so a parser that only looks for `https?://` never reaches its URL branch at all and refuses a
string stating a point in the clearest form there is. Find a schemeless `(?:[\w-]+\.)+[a-z]{2,}(?::\d+)?\/…`
and prepend the scheme. Require the host-and-path shape, or a bare `49.27, -123.09` starts being read as a
hostname.

## A directions link must be refused, not read

`/maps/dir/` is the trap among the readable forms, because it carries an `@` camera and a `data=` payload just as a
`/maps/place/` link and means something else. Measured:

- A named-waypoint route — `/maps/dir/Vancouver,+BC/Seattle,+WA/@47.6062,-122.9,8z/data=…` — has a camera
  that frames the ROUTE, not a place, so reading `@` yields a point ~40 km from the nearer end and far further from the other.
- A dir payload encodes its waypoints as `!1d<lng>!2d<lat>`, never `!3d<lat>!4d<lng>`, so the `data=` rule
  that works for a place link cannot match and the camera always wins.
- `/maps/dir/49.2827,-123.1207/Some+Hotel/@…` yields the ORIGIN — where the person right-clicked — rather
  than the destination they were locating.

So treat `dir` as a refusal with a message, not as a third subject-bearing path. `?api=1&destination=<pair>`
is the exception and reads correctly, because the pair is in a query key rather than the path.

## Which pair in a URL is the place

A `/maps/place/` URL carries two, and they are different facts:

- `!3d<lat>!4d<lng>` inside the `data=` payload is **the place's own point**.
- `@<lat>,<lng>,<zoom>z` is **the viewport centre** the link was shared at.

They agree on a link copied while looking at the pin and disagree on a shared one, where `@` is wherever the map
happened to be sitting. Prefer `!3d/!4d`, fall back to `@`. Also readable, and worth accepting: `?query=`,
`?q=`, `?ll=` and `?center=` holding a pair, and a `geo:` URI.

**Some place links have no `!3d/!4d` at all, and carry a plus code instead.** Measured 2026-10-14: a hotel
clicked out of the desktop results list gave `/maps/place/<name>/data=…!16s%2Fg%2F…!20s<8 chars>%2B<3 chars>…` —
no `@`, no `!3d`, and the `!20s` field holding a full Open Location Code with its `+` percent-encoded. That
code is the place's own point to about 3 m (11 characters) or 14 m (10), so it ranks with `!3d/!4d` and ahead
of the camera. Decoding a full code is about twenty lines: five base-20 pairs over `23456789CFGHJMPQRVWX` from
−90/−180 in cells of 20°, 1°, 0.05°, 0.0025° and 0.000125°, then each further character splits the cell 5 rows
by 4 columns; take the cell centre. Google's `open-location-code` npm package gives reference values to test
against. Read only full codes (eight characters before the `+`); a short one is relative to a locality.

## Storing a link rather than a coordinate

A `/maps/place/<name>/@<lat>,<lng>,<zoom>z/data=…!3d<lat>!4d<lng>` URL is a better thing to keep than the
pair it contains: it opens on the NAMED place with its pin, where a coordinate link drops a pin over nothing
and an address search may land on a list. Two rules make keeping one safe:

- **Trim to `origin + pathname`.** Everything after `?` is session identifiers — `entry`, `g_ep`, `skid` —
  which say which browser asked and when, and keeping them puts that in the database and every backup. The
  name and the pin both live in the path, so nothing of value is lost.
- **Only when the path names the place.** A link shared from a dropped pin carries its coordinate in
  `?q=<lat>,<lng>` and nothing in its path, so trimming it leaves a link to the whole world. Those get no
  stored URL; rebuild a coordinate link instead, which is the same destination minus the name.

Drop the `@<lat>,<lng>,<zoom>z` segment too if you can do it without breaking the path: it is the camera the
sharer happened to have, not the place, and the `data=` payload is what pins the subject.

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
