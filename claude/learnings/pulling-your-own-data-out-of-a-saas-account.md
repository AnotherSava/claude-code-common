# Pulling your own data out of a SaaS account

Getting a complete copy of your own conversations/records out of a product that has no public export API.
Learned doing a Perplexity + Comet import, but nothing below is Perplexity-specific except the examples.

## Look for the account export before writing anything

The reflex is to reverse-engineer the app's API. Check the account settings for a data export first, and
check the GDPR/CCPA help pages — "Right to Access" is frequently **self-serve** rather than a support
ticket, and the button is often filed under an unrelated heading (Account → *System*, beside *Delete
account*, not under Privacy).

It is worth doing first even when you expect the export to be poor, because of the asymmetry below.

**The export is usually the only thing that can enumerate.** This is the non-obvious part. A modern SPA
gives you no list endpoint worth having:

- the "recent items" REST endpoint is commonly **hard-capped** (20 rows) and ignores `offset`, `cursor`,
  `page`, `before`, `start`, `skip` alike — every one returns the same first page;
- the real pagination is a **persisted GraphQL query**, which rejects arbitrary query text;
- the list UI is **virtualized**, holding a fixed ~20 DOM rows however far you scroll.

So the export's *ids* can be more valuable than its *contents*. Check whether an id in the export is
accepted by the per-item endpoint — if it is, the export enumerates and the API supplies depth, and neither
alone would have been enough.

**Expect export and API to be complementary, not redundant.** Measured on one account: the export held 202
turns the API never returned (items whose id the API rejects with HTTP 400, presumably deleted server-side)
plus fields present nowhere else; the API held citations, reasoning traces and media the export flattens
away, and answer text for a handful of turns the export left blank. Keep both. Deciding which is
"authoritative" per *field* is the actual design work.

## Drive the signed-in tab; do not extract cookies

Run the fetches **in the page** of an already-authenticated tab:

```js
await fetch('/rest/thread/' + id, { credentials: 'same-origin' })
```

The session cookie is ambient, so nothing has to read, decrypt or store a credential, and the anti-bot
layer sees a genuine browser rather than a scripted TLS handshake. The alternative — decrypting the
browser's cookie store and replaying requests from a script — is both a security downgrade and the thing
that trips Cloudflare, whose failure mode is a misleading "invalid cookie".

Check the product's ToS before doing this at volume. Consumer terms commonly prohibit automated access with
no carve-out for your own data, and that is a judgement for the account holder to make explicitly.

## Getting bulk data out of the page

The page can fetch but cannot write files, and routing tens of MB through an agent's context is absurd.
Run a tiny **localhost receiver** and have the page POST to it. Two gotchas, both silent:

- **Private Network Access.** An `https://` page reaching `http://127.0.0.1` is a public→local request.
  Chrome sends a preflight carrying `Access-Control-Request-Private-Network`, and the server must answer
  with `Access-Control-Allow-Private-Network: true` **on the OPTIONS response** or the fetch never
  completes. It does not error usefully — it hangs.
- The user must also **grant the browser's prompt**. Until they do, the fetch simply never resolves, which
  is indistinguishable from a hung server.

`http://localhost` is exempt from mixed-content blocking, so the `https` → `http` hop is fine.

## Persisted GraphQL queries

Apollo/Relay persisted queries send a hash instead of the query text:

```json
{"operationName":"…","variables":{…},"extensions":{"persistedQuery":{"version":1,"sha256Hash":"…"}}}
```

Posting the query *text* returns `FORBIDDEN` — the server only honours allowlisted hashes. Two things that
follow:

- **Re-hashing the query text from the JS bundle does not work.** The bundle contains the text, but
  sha256 of what you extract will not match what the client sends.
- **Replaying a captured hash does.** Hook `window.fetch` in the page, drive the UI once to make the
  operation fire, keep the `sha256Hash`, then re-issue it with your own `variables` (different cursor,
  different filters). That is the practical way to paginate a persisted query.

The catch: hooking `fetch` only sees requests made *after* the hook is installed, and the queries you most
want usually fire during initial page load. SPA (client-side) navigation preserves the hook; a hard reload
destroys it. So reach the operation by clicking within the app, not by reloading.

## Do not trust a full-page screenshot as evidence of what you can extract

A scroll-and-stitch capture tool shows a thousand rows because it stitches **pixels** while scrolling. The
DOM at the bottom of that same scrolled page still holds ~22 rows, because the list is virtualized. A
screenshot proving "the data is all there" says nothing about whether it is reachable, and it cost real
time to discover that the two disagree.

## Count distinct things, not returned records

Paginated APIs overlap: pages repeat items, envelopes duplicate members (`first_entry`/`latest_entry`
alongside `entries`), and alias endpoints return the same item under a second id. A raw count of returned
records overstated one corpus by 6% and inverted a comparison. Dedupe on the item's own id before counting
or comparing anything, and put the dedupe in shipped code rather than in the analysis.
