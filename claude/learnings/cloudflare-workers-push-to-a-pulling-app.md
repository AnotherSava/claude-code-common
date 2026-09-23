# Waking a self-hosted app from Cloudflare, without giving it an inbound port

An app that pulls work from Cloudflare on a timer pays the interval in latency, and shortening the interval
is the wrong lever — the free Workers KV tier allows 1,000 list operations a day, so a one-minute poll
(1,440) fails outright partway through every afternoon. The fix is to stop polling for *whether* there is
work and let Cloudflare say so: the app dials out and holds a WebSocket to a Durable Object, and a Worker
sends one word down it when something arrives. The app still pulls the payload over its own authenticated
connection, so nothing new listens on the box and no ingress rule changes.

Worked out 2026-09-22 adding a wake-up channel to a mail intake that had been sweeping a KV namespace every
15 minutes. `cloudflare-email-routing-inbound.md` covers the mail half; this page is the channel.

## Why a hibernated socket rather than a long poll

Both give the same latency. They do not cost the same.

- **`ctx.acceptWebSocket(ws)`**, not `ws.accept()`. The first lets the object hibernate while the connection
  stays open at the edge; the second pins it in memory for the life of the connection.
- **`ctx.setWebSocketAutoResponse(new WebSocketRequestResponsePair('ping', 'pong'))`**, set in the
  constructor, has the edge answer the heartbeat without waking the object. The constructor is the only
  place that works: it runs again on every wake, so a pair set at connection time does not survive the
  first sleep.
- A **long-poll** request keeps the object *active* instead, which bills duration: a permanently-held
  request is roughly 11,000 GB-s a day against a free allowance of 13,000. It fits, with no headroom for a
  reconnect storm, and buys nothing the hibernated socket does not.

Durable Objects are on the free plan only with the SQLite backend, which `[exports.<Class>]` selects:

```toml
[[durable_objects.bindings]]
name = "MAIL_NOTIFIER"
class_name = "MailNotifier"

[exports.MailNotifier]
type = "durable-object"
storage = "sqlite"
```

That block is the current form; the older `[[migrations]]` with `new_sqlite_classes` says the same thing
and is deprecated. Wrangler 4.136.3 accepts `[exports]`, and `wrangler deploy --dry-run --outdir <dir>`
validates the whole config and bundle without credentials — run it before spending a deploy.

## Two Workers, because only one of them may have a door

The script that receives the document and the script that publishes an endpoint should not be the same
script. Define the Durable Object in the Worker that *has* the endpoint, and bind to it from the other with
`script_name`:

```toml
# in the receiving Worker, which keeps workers_dev = false and no routes
[[durable_objects.bindings]]
name = "MAIL_NOTIFIER"
class_name = "MailNotifier"
script_name = "trips-notify"
```

The binding does not traverse the other Worker's `fetch` handler, so the wake path is unreachable from the
internet even though the subscribe path is public. Deploy the defining Worker first — a binding to a script
that does not exist fails the deploy.

## The secret travels in the subprotocol

The WHATWG WebSocket API — which is what Node's built-in client implements — has no way to set a request
header, so `Authorization` is unavailable, and a long-lived secret in a query string ends up in logs. The
one field a client may put an arbitrary token in is `Sec-WebSocket-Protocol`:

```js
new WebSocket(url, [`bearer.${secret}`])
```

Two consequences. **Generate the secret as hex or base64url**: subprotocol values are RFC 7230 tokens, so a
passphrase containing `=`, `/` or a space makes the constructor throw. And **the server must echo the value
it accepted** in the 101 response, or a conforming client fails the connection:

```js
return new Response(null, { status: 101, webSocket: client, headers: { 'Sec-WebSocket-Protocol': offered } })
```

Check the secret in the outer Worker's `fetch`, before reaching for the object's stub, so an unauthenticated
request never costs the Durable Object a wake. Compare SHA-256 digests in a fixed-length loop rather than
the raw strings — equal-length comparison is free once both sides are 32 bytes, and the real secret's length
is itself something not to give away.

## Two account-level traps that cost the first deploy

**Cloudflare refuses every script upload until the account has a workers.dev subdomain** — error `10063`,
and `workers_dev = false` plus a custom domain does not exempt you. Wrangler tries to register one from the
working directory's name and gives up when that name is taken, which is how the error surfaces as a
confusing complaint about a name you never chose. Claim one once per account; nothing answers there while
every Worker sets `workers_dev = false`.

```bash
curl -s -X PUT "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT/workers/subdomain" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"subdomain":"<name>"}'
```

**Free Universal SSL covers one subdomain level and stops.** `a.example.com` is covered by the `*.example.com`
wildcard; `b.a.example.com` is not, and serves no valid certificate — the browser reports
`ERR_SSL_VERSION_OR_CIPHER_MISMATCH` rather than falling back to anything. Workers custom domains require
proxying, so grey-clouding is not an escape either. Either buy Advanced Certificate Manager or flatten the
name: `app-notify.example.com`, never `notify.app.example.com`.

A custom domain is otherwise the better route than workers.dev — `custom_domain = true` has Cloudflare create
the proxied record and issue the certificate, and it leaves a sibling hostname that is deliberately DNS-only
(for a Let's Encrypt HTTP-01 renewal at an origin, say) completely untouched, because that is a different
record.

```toml
workers_dev = false

[[routes]]
pattern = "trips-notify.anothersava.com"
custom_domain = true
```

**Name it after the project, not after the function.** A zone shared by several projects is a shared
namespace exactly like a docker bridge or a flat `conf.d`, and `notify.example.com` is a claim staked in it.
A hostname belongs to exactly one Worker, so the first project to take the generic name takes it from
everyone. Nothing scarce is being conserved by sharing: a zone allows 100 custom domains and 1,000 routes,
identical on free and paid, and one Worker may carry several.

## What the client side has to do

A dropped flow delivers no close event — it simply stops carrying traffic — so from the app's end a dead
socket and a quiet week look the same. The heartbeat is what tells them apart: send `ping` on an interval
shorter than the shortest NAT idle timeout in the path (45s is comfortable), and close the socket yourself
when no `pong` arrives within a deadline. Cancel that deadline when the `pong` does arrive; forgetting to is
a bug that kills a healthy connection on a timer.

Three more that are easy to leave out:

- **Sweep on connect, not only on a wake.** Anything that arrived while the socket was down is still queued,
  and no wake for it will ever be sent again — the wake is an event, and that connection missed it.
- **Coalesce.** Several messages produce several wakes, and the first sweep takes them all; the rest want one
  further look, not one sweep each. Hold the in-flight promise and a dirty flag.
- **Keep the timer.** A push channel that has quietly stopped is indistinguishable from a quiet week, so the
  poll stays as the floor underneath — just at a longer interval. Report the channel's state somewhere a
  human can read it; that is the only place the difference is visible before mail goes missing.

## Minting a token for the deploy

Three permission groups cover this, and the first two are account-scoped while the rest are zone-scoped, so
the token needs two policies. Group ids are stable and account-independent:

| Group | Id |
|---|---|
| Workers Scripts Write | `e086da7e2179491d91ee5f35b3ca210a` |
| Workers KV Storage Write | `f7f0eda5697f475c90846e879bab8666` |
| Workers Routes Write | `28f4b596e7d643029c524985477ae49a` |
| DNS Write | `4755a26eedb94da69e1066d98aa820be` |
| Zone Read | `c8fed203ed3043cba015a93ad1616f1f` |

There is no separate Durable Objects group; Workers Scripts Write covers them.

**A general-purpose token's silence is not evidence.** `GET /accounts/{a}/workers/scripts` answered
`success: true` with an empty array on an account that demonstrably had Workers, because the token lacked
the permission — the same shape as a genuinely empty account. `GET …/workers/subdomain` and
`…/workers/scripts/{name}` both answer `403` in that case, so probe an endpoint that distinguishes them, or
mint a token that can actually see what you are asking about.

## Related

- `cloudflare-email-routing-inbound.md` — the mail side: the permission map, the KV queue shape, and why the
  app pulls rather than being pushed a document.
- `cloudflare-pages-deploy.md` — token gotchas that apply to every Cloudflare API.
