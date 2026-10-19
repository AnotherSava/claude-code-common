# Extracting travel bookings from confirmation emails

Parsing "your booking is confirmed" mail into structured data. Verified August 2026 against a real mailbox and
a real `kitinerary-extractor` run.

## Three tiers, cheapest first

| Tier | Reads | Covers |
|---|---|---|
| schema.org JSON-LD in the HTML | free, exact | a minority of senders |
| KItinerary | email, PDF, pkpass, ics, boarding-pass barcodes | 30 airlines, 32 rail/bus operators, 10 lodging providers |
| An LLM | plain text, or text pulled out of a PDF | everything else, any language |

Order matters for cost, not taste. Reaching the LLM for a document that carries JSON-LD is paying for an answer
already written in the page.

## Which senders actually embed JSON-LD

Google's Gmail email-markup programme is alive (no deprecation notice as of Aug 2026), but adoption is thin.
Checked by fetching full `htmlBody` and grepping for `<script type="application/ld+json">`:

- **Ship it:** Airbnb (`LodgingReservation`), Alaska (`FlightReservation`), FlixBus/Greyhound
  (`BusReservation`), Hotels.com (`LodgingReservation`, present since at least 2018).
- **Do not:** Booking.com, Air Canada, WestJet, Expedia, United, Delta, Agoda, Amtrak, Kiwi, Trip.com.
- **Nobody** used microdata. Do not bother with it.

Two shapes to handle: a payload may be a single object **or a JSON array with one element per leg** (Alaska
does this). Parse as a list or you keep only the outbound flight.

## The timezone trap, which is the real work

An offset in the payload is not a timezone, and several senders get it wrong:

- **Alaska, FlixBus** — correct UTC offsets. Trustworthy.
- **Airbnb** — naive local wall time, no offset. Correct, but the zone has to come from the address.
- **Hotels.com** — stamps **Expedia's US-Central server offset** on properties anywhere in the world, and
  reports check-in as midnight. A 2018 Sendai booking claimed `-0500` for a JST hotel. Believing either the
  offset or the time-of-day puts check-in on the wrong day once converted.

So: store **wall time plus an IANA zone**, never an instant alone, and record per-sender how much to trust the
stated time. Deriving the zone from the address works for single-zone countries; for the US, Canada, Australia,
Brazil and Russia it cannot, and "unresolved" is the honest answer — a guessed UTC looks authoritative and
reads back as the wrong hour.

Airport code → coordinates: **OurAirports** `airports.csv` (public domain, ~10 MB, filter to rows with an IATA
code and drop `closed`/`heliport`/`seaplane_base` — about 8,800 remain, 360 kB as a compact JSON map).
Coordinates → IANA zone: **`tz-lookup`** on npm (CC0, offline, no API key). Neither needs a network call.

## KItinerary

KDE's extraction engine, and the same one the TREK self-hosted planner uses.

- **Package:** Debian `libkitinerary-bin` (in stable), Alpine edge `kitinerary`. Not a package named after the
  binary.
- **Binary path carries the architecture triplet** — `/usr/lib/x86_64-linux-gnu/libexec/kf6/kitinerary-extractor`,
  `aarch64-linux-gnu` on Apple silicon. Resolve it at image build (`find /usr/lib -name kitinerary-extractor`)
  and symlink to a stable name; hardcoding the path builds on one architecture and fails on the other.
- **Reads a file, not stdin**, and uses the suffix to tell an `.eml` from a `.pdf`. The wrong suffix silently
  falls back to generic extraction and returns less.
- **Set a UTF-8 locale.** It is a Qt program; a slim image leaves it in POSIX, so it prints a warning on every
  invocation and does its text handling outside UTF-8. `ENV LANG=C.UTF-8 LC_ALL=C.UTF-8`. This matters for
  Russian, Japanese and French confirmations, and the warning matters separately if you parse its stderr.

### Its output is schema.org, but not the dialect you read out of HTML

This is the trap. `kitinerary-extractor --output json` prints `JsonLdDocument::toJson`, which differs from
embedded email JSON-LD in two ways:

- A zoned time is an **object**, not a string:
  `{"@type":"QDateTime","@value":"2018-07-20T12:25:00+02:00","timezone":"Europe/Berlin"}`.
  A parser that only accepts strings gets `null` and declines the document.
- Lodging is **`checkinTime` / `checkoutTime`**, not `checkinDate` / `checkoutDate`.

A mapper written against the HTML dialect therefore returns nothing for every document KItinerary parsed
correctly — and the failure is silent, because "extracted nothing" and "declined" look identical. Everything
then falls through to the expensive LLM tier, which is precisely what the tier ordering exists to prevent.

Take the `timezone` field seriously: it is a real IANA name, and it is exactly what cannot be inferred from a
US or Canadian address. It is worth more than the offset beside it.

A few extractor scripts emit the bare travel object (`Flight`, `LodgingBusiness`) with no reservation wrapper —
wrap it before mapping.

## PDF and other attachments

A large minority of senders put the authoritative detail only in an attachment: Amtrak, Trip.com, Agoda, Kiwi,
Omio, Lufthansa, Hertz, and airline "itinerary and receipt" mail. KItinerary reads PDFs natively including the
barcode; when it declines, `pdftotext -layout` preserves the column structure of an itinerary table well enough
for an LLM. Kiwi and Omio also attach per-segment `.ics`, which is as deterministic as JSON-LD — but gate that
path on the specific sender, because a generic `has:attachment filename:ics` sweep is dominated by ordinary
meeting invites.

**KItinerary will not turn those calendar parts into a booking, so do not plan a tier around it.** Measured
2026-09-24 on a four-leg flight confirmation carrying one `VEVENT` per leg: the extractor answered "nothing
found" for the whole `.eml`, and answered the same for a single 604-byte `.ics` handed to it alone with the
right suffix. The data is deterministic; the engine still declines it.

What is worth doing instead costs nothing — **append the calendar text to whatever the LLM tier reads.** It
arrives as text, so unlike a PDF it needs no extractor call, and roughly 600 characters per leg carry the
carrier, the flight number, both endpoints and exact `DTSTART`/`DTEND` instants: the facts the model is
otherwise left to infer from marketing HTML. Match on the filename as well as the MIME type, because senders
label these `application/ics`, which is not the registered type — `text/calendar` is.

## Boarding passes: the barcode is the test, and two traps around it

An IATA boarding-pass barcode (BCBP) is the reliable way to tell a boarding pass from every other attachment.
KItinerary decodes it into a `FlightReservation` whose `reservedTicket.ticketToken` is the payload behind its
format, `aztecCode:M1…` (`M`, then the leg count), and whose `reservationFor` carries the airline code, flight
number and `departureDay`, with `airplaneSeat` beside it. An itinerary or e-ticket PDF can yield a
`FlightReservation` too, but without a BCBP token, so test the token rather than the type. Measured 2026-10-18
across five airlines' pass mail and four non-pass PDFs (e-ticket, itinerary, terms, an insurance `.pkpass`): no
false positive, and one pass PDF named two legs of a connection.

- **It misses the barcode in a full-size image.** A 750×1334 phone-screen JPEG pass with an Aztec code on a
  coloured background came back "nothing found", and so did a thresholded black-and-white copy. A crop around the
  code decoded fine. ZXingReader (Debian `zxing-cpp-tools`, the CLI over the same zxing-cpp library KItinerary
  links) reads the whole image; `ZXingReader -1 <file>` prints one `<path> <format> "<text>"` line per barcode,
  `<path> None` when there is none, and exits 255 with `Failed to read image` for a file that is not an image.
  Hand the decoded text back to KItinerary as a `.txt` file and it parses the BCBP string just as it does one
  from a PDF.
- **The year comes from `--context-date`, and no context gets it right at every boundary.** BCBP dates the
  flight by day of the year, plus (optionally) the last digit of the issue year. KItinerary places that digit in
  the context's decade, ten years back when that lands after the context's year, and dates the flight to the
  first occurrence of its day on or after the issue date; with no issue date, on or after the context. With no
  context at all it uses today: given 2024 for a pass issued in 2026, it returned 2016. Measured 2026-10-18 on
  the sidecar, the context date's two failure directions:
  - **Context = the message's send time** dates a pass with no issue date a year late when it was sent after
    its flight, or on its departure evening west of UTC (the UTC date has already rolled over).
  - **Context moved earlier to avoid that** puts a pass issued on 1 January into the previous year, where the
    issue digit is read a decade back: 2017-01-02 for a 2027 pass with a context 12 hours before the send.

  What works: pass the send time, then keep KItinerary's **day of the year** and choose the year nearest the
  send. Keep the day of the year, not the month and day — counted in a year of the other leap-ness, a date after
  28 February moves by one. Day 366 exists only in a leap year, so with none near the send keep KItinerary's date.

## Modelling notes that came out of the data

- **Cancellations are first-class.** The same confirmation code arrives confirmed and later cancelled; a naive
  import resurrects stays that never happened. Keep a tombstone — code, provider, date, status — and nothing
  else.
- **One code arrives many times.** A single airline PNR turned up across a confirmation, two check-in nudges,
  two boarding passes and two "we've updated your itinerary" mails. Deduplicate on `(provider, code)` and let
  the newest supersede.
- **The provider must come from the sender address, not the payload.** Airbnb's markup names the *listing* and
  never mentions Airbnb, so a payload-derived provider changes when a host renames their listing — and it is
  half the dedup key.
- **`addressCountry` may be a full country name.** Truncating to two characters turns "Germany" into `GE`,
  which is Georgia. Map known names, and return null rather than a wrong-but-valid code.
