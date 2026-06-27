# Resend transactional email + Porkbun DNS verification

How to wire a custom-domain sender on Resend and add the verification records via the Porkbun DNS API. Provider mechanics learned setting up operator/customer email for a Next.js app.

## Resend

- **Transport seam by env:** a typical integration selects the transport from the environment — with `RESEND_API_KEY` set, mail goes out via Resend; without one, a console transport logs it. So local dev sends nothing and needs no setup; dropping the key in flips on real delivery with no code change.
- **Sandbox sender `onboarding@resend.dev`:** always available, needs **no domain verification** — but it **only delivers to the email address that owns the Resend account.** Perfect for testing a self-addressed alert (e.g. an operator-outage email to yourself); useless for customer mail to arbitrary recipients.
- **Custom-domain sender:** Resend rejects any send whose `from` is on an **unverified** domain — the API returns an error like *"The `<domain>` domain is not verified. Please add and verify your domain."* The send call doesn't throw at the network layer; the rejection is in the response body (`error` field), so a transport that only checks for thrown errors will silently swallow it — surface `error` as a throw.
- **Restricted (send-only) API keys:** a key created as "sending access" returns `401 {"name":"restricted_api_key","message":"This API key is restricted to only send emails"}` on **read** endpoints (e.g. `GET /domains`). So you can't introspect domain-verification status with a send-only key — verify in the dashboard or with a full-access key.
- **Verify deliverability fast** with a one-off direct send (bypassing app code) to isolate "is the key + from + recipient combination accepted":
  ```js
  const { Resend } = require('resend');
  const r = new Resend(process.env.RK);
  const { data, error } = await r.emails.send({ from, to, subject, text });
  console.log(error ? 'ERROR: ' + error.message : 'OK id=' + data.id);
  ```

### Managing domain verification via the API (full-access key)

A full-access key (not send-only) drives the whole verify flow without the dashboard:

```bash
# list domains → id, status, region
curl -s https://api.resend.com/domains -H "Authorization: Bearer $RK"
# get one domain → expected records + per-record status
curl -s https://api.resend.com/domains/$ID -H "Authorization: Bearer $RK"
# trigger verification after the DNS records are live
curl -s -X POST https://api.resend.com/domains/$ID/verify -H "Authorization: Bearer $RK"
```

- Domain `status` lifecycle: `not_started` → `pending` (right after POST `/verify`) → `verified` (or `failure`). Verification is **asynchronous** — poll `GET /domains/:id` every ~15s; it typically flips within a minute once records resolve.
- `GET /domains/:id` returns the exact `records` Resend expects (DKIM/SPF values) — diff these against live DNS to spot a mismatch before triggering verify.
- Keep the full-access management key **separate** from the app's send-only key (different blast radius); store it outside the app, alongside other registrar/infra creds.

### Resend domain DNS records (Amazon SES under the hood)

Resend shows these on the domain page; the SPF/feedback host is **region-specific** (e.g. North Virginia → `us-east-1`):

| Purpose | Type | Host (subdomain) | Content | Prio |
|---------|------|------------------|---------|------|
| DKIM | TXT | `resend._domainkey` | the long `p=…` public key | — |
| SPF (bounce) | MX | `send` | `feedback-smtp.<region>.amazonses.com` | 10 |
| SPF | TXT | `send` | `v=spf1 include:amazonses.com ~all` | — |
| DMARC (optional) | TXT | `_dmarc` | `v=DMARC1; p=none;` | — |

"Enable Receiving" is a separate, optional feature for **inbound** mail — skip it for a send-only app (the `send` MX above is for bounce feedback and IS part of sending). DKIM resolves as one TXT; the `p=` value is the complete record content.

## Porkbun DNS via API

Porkbun exposes a JSON API, far more reliable than driving their web UI. Prereqs: create an account API key (**Account → API Access** → `pk1_…` + secret `sk1_…`) **and** flip the per-domain **API ACCESS** toggle on (off by default; otherwise calls are rejected).

```bash
# verify creds
curl -s -X POST https://api.porkbun.com/api/json/v3/ping \
  -H 'Content-Type: application/json' \
  -d '{"apikey":"pk1_…","secretapikey":"sk1_…"}'        # → credentialsValid:true

# create a record — `name` is the SUBDOMAIN ONLY (Porkbun appends the domain); add `prio` for MX
curl -s -X POST https://api.porkbun.com/api/json/v3/dns/create/<domain> \
  -H 'Content-Type: application/json' \
  -d '{"apikey":"pk1_…","secretapikey":"sk1_…","type":"TXT","name":"resend._domainkey","content":"p=…","ttl":"600"}'

# list everything (debugging / spotting parking records)
curl -s -X POST https://api.porkbun.com/api/json/v3/dns/retrieve/<domain> -H 'Content-Type: application/json' -d '{"apikey":"…","secretapikey":"…"}'
```

- `name`: subdomain only, **no domain suffix** (root = empty string). TXT content goes in raw, **no wrapping quotes**.
- MX needs `"prio":"10"`; TXT/DKIM store `prio:"0"` harmlessly.

### Porkbun gotchas

- **Parking records:** a fresh domain ships with an apex `ALIAS` and a `*` wildcard `CNAME`, both → `pixie.porkbun.com` (their parking page). A wildcard CNAME does **not** shadow a name that has explicit records (RFC 4592 — "the wildcard only synthesizes for names with no other data"), so the Resend records win once created. Replace/remove the parking ALIAS + wildcard when the real site deploys.
- **Cloudflare-backed edge lag:** Porkbun serves DNS via Cloudflare (`"cloudflare":"enabled"` in the retrieve response). Right after a create, the authoritative servers can **briefly return the parked `pixie.porkbun.com` value** for a new `send`/`_dmarc` name before the edge updates — re-query a moment later, directly against an authoritative NS, before concluding it's wrong:
  ```bash
  dig +short TXT send.<domain> @salvador.ns.porkbun.com   # confirm the real value, not pixie
  dig +short MX  send.<domain> @maceio.ns.porkbun.com
  ```
- Keys grant **full DNS control** — don't persist a registrar API key in an app's `.env` (the app doesn't read it, and the blast radius is the whole domain); keep it in a password manager and paste when needed.

## App-side reminders

- `EMAIL_FROM` (sender) must match a verified domain in prod; while waiting on verification, keep `onboarding@resend.dev` so self-addressed alerts still deliver, then switch to the real address once verified.
- `APP_BASE_URL` builds absolute links inside emails (tracking/admin URLs); set it to the real `https://…` host in prod (defaults to localhost otherwise).
