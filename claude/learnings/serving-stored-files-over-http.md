# Serving a stored file over HTTP

An app that stores uploads and hands them back — a boarding pass, an invoice, a photo — spends the file's own
name in a response header. That is where a route which works on every file you tested answers 500 on a file a
real person uploaded, because the name came from a file picker and the header can only carry a subset of what
a filename may hold.

Measured on Node 24.19.0 with the WHATWG `Response`/`Headers` (Next 16 route handlers, Deno, Bun and
Cloudflare Workers share the semantics, since they come from the Fetch spec rather than from Node).

## A header value is a ByteString, so a name above U+00FF throws

Every header value is a sequence of bytes 0x00–0xFF. Constructing a response whose header holds a code point
above U+00FF raises `TypeError: Cannot convert argument to a ByteString because the character at index N has a
value of 1041 which is greater than 255` — before any response object exists, so a handler with no try/catch
answers 500 and the file is unreachable rather than mis-named.

```js
new Response(bytes, { headers: { 'content-disposition': 'inline; filename="Билет.pdf"' } })  // throws
new Response(bytes, { headers: { 'content-disposition': 'inline; filename="café.pdf"' } })   // passes
```

Latin-1 passing is the trap underneath the trap: `café.pdf` is emitted as latin-1 bytes with no charset
declared, so the browser saves a mojibake name. And a name holding CR or LF throws differently —
`TypeError: Headers.append: … is an invalid header value` — which is header injection being refused, so strip
those rather than encoding them.

Non-ASCII filenames are ordinary, not exotic. In one real mailbox corpus 26 of 239 attachment names were
outside Latin-1 — Cyrillic and CJK — and one that read as ASCII at a glance was not: an itinerary named
`<dates>_City—City—City.pdf` carries an em dash (U+2014), which throws exactly like Cyrillic does.

## RFC 6266: send both parameters, never one

The fix is the standard's own two-parameter form. `filename*` carries the real name percent-encoded as UTF-8
and every current browser prefers it; the plain `filename` beside it is an ASCII skeleton for anything that
reads only that one.

```js
function contentDisposition(filename) {
  const skeleton = filename.replace(/[^\x20-\x7e]/g, '_').replace(/["\\]/g, '_');
  // encodeURIComponent leaves four characters RFC 5987's attr-char does not allow.
  const encoded = encodeURIComponent(filename).replace(/['()*]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
  return `inline; filename="${skeleton}"; filename*=UTF-8''${encoded}`;
}
```

Two details that are easy to get wrong:

- **The skeleton replaces rather than drops.** Keeping one `_` per lost character preserves the extension and
  the length, so a reader seeing only the plain parameter still gets a usable name. Dropping them can produce
  an empty name or one with no extension.
- **`encodeURIComponent` is not RFC 5987 encoding.** It leaves `'`, `(`, `)` and `*` unescaped, and none of
  them is an `attr-char`; `!` and `~` are, so they can stay. It also throws `URIError: URI malformed` on an
  unpaired surrogate, which is the one input that defeats this function — decide deliberately whether that is
  reachable in your pipeline.

## `inline` from your own origin runs the file's script

`content-disposition: inline` is what makes a PDF or an image open in the browser's own viewer instead of
downloading, which is usually the point. It also means an uploaded `.html` or `.svg` executes script **on the
origin that served it**, with that origin's cookies and storage — `X-Content-Type-Options: nosniff` does not
help, because the type is not being sniffed, it is being obeyed.

The choices are to serve `attachment` for anything outside an allowlist of types, to serve files from a
separate origin, or to accept it on an app where the only uploader is the operator. Decide which; the default
of storing a browser-supplied `content-type` and echoing it back `inline` is the permissive one.

## Content-addressed storage makes the response cacheable for good

Where the URL carries the content's own digest, the bytes behind it can never change, so
`cache-control: private, max-age=31536000, immutable` is exactly true rather than optimistic. Keep `private`
on anything behind a shared password or a VPN, so an intermediary cannot hold a copy.
