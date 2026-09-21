# A forwarded email is not the email — what survives, what a parser sees, and what to test with

Any system that accepts "forward me your confirmation" is parsing a document the user's mail client
rewrote. The rewrite removes the structured data first, the sender second, and leaves prose that looks fine
in every fixture you would think to write. Found 2026-09-21 building a forwarding intake whose unit tests
all passed against fixtures that shared none of a real forward's properties.

## Gmail's inline forward strips the schema.org block

A vendor whose confirmation carries `<script type="application/ld+json">` — Airbnb, Alaska, FlixBus,
Hotels.com and most travel senders — loses it the moment it is forwarded inline. The forwarded copy of a
FlixBus confirmation carried **no `<script>` tag at all**, sanitized out with the rest of the scripting when
Gmail re-rendered the original into the new message body.

The consequence is a tier change, not a degradation: a document that a structured-data reader handles for
free arrives needing a language model. Say so wherever someone chooses how to forward, because
**"forward as attachment" is the difference** — that route encodes the original as a `message/rfc822` part,
intact, headers and markup included.

## A mail body is a fragment, and a document-tag sniff misses it

Deciding "is this HTML?" with `/<html|<body|<script/` is wrong for email. Gmail's forward body opens
`<div dir="ltr">` and contains none of the three, so an email that is nothing but markup reads as plain
text. Match block-level tags instead, and require a delimiter after the tag name so arithmetic and
emoticons do not become markup:

```js
const looksLikeHtml = (t) => /<(html|body|script|div|table|tbody|tr|td|p|span|a|ul|li|img|br|h[1-6])[\s>/]/i.test(t);
```

Quoted-printable is a separate trap on the same line of code, and the two are easy to confuse: a QP body
leaves `<div` literal, so the fragment problem is what actually fires, but a **base64** part leaves nothing
readable at all. Both are fixed by decoding through a MIME parser rather than sniffing the source.

## Different tiers want different parts of the same message

One `.eml` is not one document:

- A **structured-data reader** wants the decoded HTML part.
- **kitinerary** wants the whole raw message — it reads attachments, barcodes and pkpass files out of it,
  and a large class of senders puts the entire itinerary in a PDF with a covering letter as the body.
- A **language model** wants the decoded text, and is charged for whatever it is sent. A real forwarded
  confirmation measured 444 KB of raw MIME against an 11 KB HTML part; the difference was a base64 boarding
  pass it could not read.

So decode once, keep the raw bytes, and hand each tier its own view.

## Recovering the original sender

The envelope `From` of a forward is the forwarding mailbox, which is worse than useless when the sender
address identifies the vendor — Airbnb's markup names the listing and never names Airbnb, so the address is
the only thing that says which platform issued the code.

**Position, not the word before the colon.** `From`, `De`, `От` and `差出人` are the same field and the list
of translations never ends. Every client writes the sender first — Gmail as From/Date/Subject/To, Outlook
as From/Sent/To/Subject, Apple Mail as From/Subject/Date/To — so the first quoted line carrying an address
is it, in any language.

Find the quoted block by shape rather than wording: dashes-text-dashes survives localization
(`---------- Пересланное сообщение ---------`, `-----Исходное сообщение-----`) where the words do not. A
bare run of hyphens is a divider and matches half the confirmations ever sent, so require letters between
two dash runs. Then require **two or more adjacent `Label: value` lines** before believing any of them; one
such line is prose with a colon in it.

When recovery fails, keeping the envelope sender beats nulling it. A personal mailbox matches no vendor
pattern, so the downstream provider lookup falls through to the payload, while nulling would also strip the
sender from a message that was sent directly rather than forwarded.

## Test with a message that has a real message's properties

Hand-written fixtures share none of what breaks: they are unencoded, document-shaped, single-part and
ASCII. A fixture set worth having includes a quoted-printable part, a base64 part, a `multipart/mixed` with
an attachment large enough that "did tier 3 get the attachment" is answerable by length, a fragment body
with no `<html>`, and a localized forward block. The library-level check — does the parser decode this —
is not the check that matters; what matters is which part each consumer ends up holding.

## postal-mime

`postal-mime` is **MIT-0**, not AGPL as several summaries claim — check the package rather than the
write-ups if licensing decides it. It runs in Node and in Workers with no Node dependencies, decodes
transfer encodings and RFC 2047 encoded-words, and with `forceRfc822Attachments: true` surfaces a nested
`message/rfc822` part as an attachment you can re-parse, which is how a forward-as-attachment gets
unwrapped to the original.

## Related

- `cloudflare-email-routing-inbound.md` — how the mail reaches the parser in the first place.
- `kitinerary-booking-extraction.md` — what the parser does with it once it has the right bytes.
- `gmail-api.md` — reading the mailbox rather than receiving from it.
