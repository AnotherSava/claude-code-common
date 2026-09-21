# Cloudflare Email Routing — receiving mail into an app, and the permissions that hide from you

Giving an app an inbound address costs nothing at Cloudflare and no SMTP server anywhere: Email Routing
takes delivery, an Email Worker runs on each message, and the Worker can put it wherever the app can reach.
What costs an evening is the token — four of the five endpoints in this flow sit behind permission groups
whose names do not contain the words you searched for.

Worked out 2026-09-21 wiring a forwarding address into a Next.js app on a shared VPS.

## The permission map, which is the whole difficulty

| Endpoint | Permission group | Scope |
|---|---|---|
| `GET/POST /zones/{z}/email/routing`, `…/routing/enable` | **Zone Settings** | zone |
| `GET/POST /zones/{z}/email/routing/rules` | **Email Routing Rules** | zone |
| `GET /accounts/{a}/email/routing/addresses` | **Email Routing Addresses** | account |
| `…/storage/kv/namespaces/…` | **Workers KV Storage** | account |
| `wrangler deploy` | **Workers Scripts** | account |

**The settings and enable endpoints are not governed by any Email Routing group.** They answer to Zone
Settings, because Cloudflare files them as generic zone settings. Searching the token editor for "email"
finds three groups, none of which unblocks `enable`, and the failure is a flat `10000 Authentication error`
with nothing naming what is missing. This is the single most expensive fact on this page.

**Three separate groups have "Email Routing" in the name and they are not interchangeable.** Adding
*Addresses* (account-scoped) when you wanted *Rules* (zone-scoped) is easy, produces working reads, and
still refuses every rule write.

**A successful GET does not tell you which permission granted it.** `GET …/email/routing/rules` answered
200 on a token carrying no Email Routing group at all — evidently off Zone Settings — while the matching
POST refused. Inferring "they granted Read but not Edit" from that was wrong twice over. Read the token's
actual policies instead of inferring them from probes; see the Pages learning for that endpoint, and note
it needs **API Tokens Read**, which a working token usually does not have.

## Minting a token from a token

`POST /accounts/{a}/tokens` needs **API Tokens Write** and refuses with `403 9109 Unauthorized to access
requested resource` — an authorization refusal, not a complaint about the payload, so an empty `policies:[]`
probe distinguishes "may not create" from "created something wrong" without creating anything.
`GET …/tokens/permission_groups` needs API Tokens Read and refuses the same way, so a token that cannot
mint also cannot look up the group ids it would need.

A dedicated token whose only permission is API Tokens Write is a reasonable thing to keep in the ad-hoc
credential store: it mints and revokes, and it is revocable on its own without touching the general-purpose
token. It is also account-root in effect — anything that can create a token can create one with every
permission — so it is the wrong thing to add to a token that already does day-to-day work.

Permission group ids are stable and account-independent. `Workers KV Storage Write` is
`f7f0eda5697f475c90846e879bab8666`.

## Enabling it

`POST /zones/{z}/email/routing/enable` adds and **locks** the records: three MX at the apex pointing at
`route1|2|3.mx.cloudflare.net`, an SPF TXT (`v=spf1 include:_spf.mx.cloudflare.net ~all`), and a DKIM TXT
at `cf2024-1._domainkey`. Check what the zone already carries first — this is destructive to an existing
mail setup and silent about it.

Those MX records coexist with a **proxied apex CNAME** to a Pages site. Cloudflare's CNAME flattening makes
the apex a normal name with records of several types, so a zone whose root serves a website can still
receive mail.

A routing rule pointing at a Worker needs no verified destination address; only `forward` actions do.

```bash
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE/email/routing/rules" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"intake","enabled":true,
       "matchers":[{"type":"literal","field":"to","value":"plans@example.com"}],
       "actions":[{"type":"worker","value":["my-email-worker"]}]}'
```

Subdomains are supported (`inbox.example.com`), but routing a subdomain while the apex keeps someone else's
MX is not a flow the onboarding offers. Where the apex has no mail, use it and skip the question.

## The Worker

An Email Worker exports `email(message, env, ctx)` rather than `fetch`. `message.raw` is a ReadableStream of
the complete MIME message and `message.rawSize` its length; the platform refuses anything over 25 MiB
before the Worker sees it. `message.setReject(reason)` refuses at SMTP, which tells the sender and costs no
storage — the right place for a sender allowlist on an address anyone can guess.

**Set `workers_dev = false` in `wrangler.toml`.** A Worker with no HTTP route still triggers a workers.dev
publish, and on an account that has never registered a workers.dev subdomain the deploy dies with
*"could not automatically register … as your workers.dev subdomain because the name is unavailable"* before
uploading anything. An inbound-mail Worker wants no HTTP endpoint anyway.

`wrangler deploy` then prints `No targets deployed` and that is success: the trigger is the routing rule,
not a route.

## Shape that avoids a public webhook

The obvious wiring — Worker `fetch()`es the app — puts a public write endpoint on an app that may not want
one. Writing the raw message to a KV namespace and having the app pull on a timer keeps every ingress rule
intact, at the cost of the poll interval. KV values take arbitrary bytes, so the message goes in whole; key
it `<ISO timestamp>-<hash prefix>` so a list comes back in arrival order.

Give the puller its own token with Workers KV Storage Write and nothing else. The Worker needs no token at
all — it writes through its binding.

**Set no `expirationTtl` on queued mail.** A queue that empties itself is indistinguishable from one nothing
ever arrived in, and the thing being queued is the only copy outside the sender's Sent folder.

## Related

- `cloudflare-pages-deploy.md` — token gotchas that apply to every Cloudflare API: the `cfat_` verify
  endpoint, editing a token keeping its secret while Roll changes it, and reading a token's real policies.
- `forwarded-email-parsing.md` — what actually arrives when a human forwards a confirmation.
