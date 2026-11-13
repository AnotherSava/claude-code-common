# Brevo for transactional SMTP

Brevo's free plan is the fallback when a project's sign-in or notification mail needs an allowance of its own and
Resend's free account is already spoken for. Resend's acceptable-use policy forbids a second free account opened
to get around its quota, so "one more free Resend account" is not an option. Measured 2026-11-12/13 while setting up
a Pocket ID instance's login-code mail. A statement that comes from one of Brevo's pages and was not exercised says
so.

## Two kinds of key, told apart by prefix

| Key | Prefix | Works for |
|---|---|---|
| API key | `xkeysib-` | the REST API at `https://api.brevo.com/v3`, header `api-key: <key>` |
| SMTP key | `xsmtpsib-` | the SMTP relay only, as the password |

Both are generated under **Settings → SMTP & API**, on different tabs, and each is shown once. The REST API answers
a `401` with `Key not found` to any string it never issued as an API key, an SMTP key included, so the wrong kind of
key reads like a revoked one. Check the prefix first, and guard a clipboard-to-Doppler store on it, so the wrong
kind is refused before it overwrites anything.

## A key unused for 90 days is deactivated

Either kind is switched off after 90 days without a successful call or send, whatever expiry it was created with.
Brevo mails a reminder 7 days ahead, and the key can be reactivated on the page that created it (the "Create and
manage your SMTP keys" and "Create and manage your API keys" help articles, read 2026-11-13; not exercised). A
sign-in service whose users mostly come in by passkey can go that long without mailing a code, and would find its
key off the next time it needs one.

## The relay

- The host is `smtp-relay.brevo.com`. Ports 587 and 2525 take STARTTLS and port 465 takes implicit TLS. The key
  logged in on 587 and 465; 2525 was only seen to offer STARTTLS.
- The login is a generated address on the `smtp-brevo.com` domain for a recently created account, and the account's
  own login address for an older one (Brevo's SMTP troubleshooting page). It is not a secret, and the API returns it
  as `relay.data.userName` in `GET /v3/account`.
- The From address was registered as a sender (`POST /v3/senders` with `name` and `email`). On an authenticated
  domain it is active at once, with none of the code verification a new sender otherwise needs. Registering may not
  be required at all: Brevo's SMTP troubleshooting page allows "a verified sender address or a domain-authenticated
  address" in From, and a send from an unregistered address was not tried.

## Authenticating a sending domain through the API

A `POST /v3/senders/domains` with the domain name returns the records Brevo wants, and reading the domain back
with `GET /v3/senders/domains/<domain>` lists them with a status each. It asked for these:

| Type | Name | Value shape |
|---|---|---|
| CNAME | `brevo1._domainkey` | `b1.<domain-dashed>.dkim.brevo.com` |
| CNAME | `brevo2._domainkey` | `b2.<domain-dashed>.dkim.brevo.com` |
| TXT | apex | `brevo-code:<hex>` |
| TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:` and Brevo's report mailbox, `rua` at `dmarc.brevo.com` |

The `_dmarc` value is what Brevo offers a zone that has no DMARC record. A zone with one keeps its own, and Brevo's
domain-authentication help page asks only that it carry a `rua` tag. The same page says an account can be given a
single DKIM TXT record in place of the two CNAMEs (read 2026-11-13, neither exercised).

No SPF or MX record is involved; that page gives those out only with a dedicated IP. The envelope sender of the
delivered mail is on a Brevo domain, so SPF passes there, and DMARC passes through the DKIM signature, which is
made in the sending domain's name.

Once the records exist, a `PUT /v3/senders/domains/<domain>/authenticate` asks Brevo to check them. Thirty seconds
after they were written at Cloudflare, as DNS-only records, every one passed and the domain read back as
authenticated.

## What Brevo changes in the mail

Seen in the source of one delivered login-code mail:

- **Click tracking rewrites every HTML link** to a redirect on a `sendibt2.com` subdomain. A sign-in link then
  points at a third-party domain, and where the mail prints the address as the link's text, the text and the target
  no longer match. The plain-text part is left alone, and a typed code is unaffected.
- Image sources are rewritten to paths on the same domain.
- An open-tracking pixel is added, and a `List-Unsubscribe` header with its one-click `List-Unsubscribe-Post`.
- No "Sent with Brevo" badge was added, though the free-plan FAQ says the plan's mail always carries one.
- At Gmail, DKIM and DMARC passed for the sending domain, and SPF for Brevo's envelope domain.

Turning tracking off is done by Brevo's support and not by a setting. Its product manager wrote on the community
forum in 2024 that disabling is available on request, to Enterprise customers only. Users who asked support anyway
report both outcomes: switched off within a day (issue 115 of `sendinblue/APIv3-nodejs-library` on GitHub, November
2025, plan not stated), and refused after an account review (the same issue, March 2024; the forum thread "No Way
to Disable by Option tracking in Transactional E-Mail", January and June 2025). The request made for the account
measured here was open when this was written.

## The daily allowance fails silently

The free plan allows 300 email sends a day. Past that, Brevo holds up to 1,000 more transactional mails in a retry
queue and does not deliver the rest (free-plan FAQ, read 2026-11-13). Its SMTP troubleshooting page describes mail
over the allowance as queued and paused, so the sending app logs a success and the mail arrives once the allowance
resets. What the relay answers past the queue is not documented, and none of this was exercised. For a login code
with a 15-minute life, arriving the next day is the same as not arriving. The remaining allowance is the `credits`
value under `plan[]` in `GET /v3/account`, which read 299 after the day's first mail.

## Authorized IPs

From Brevo's help article "Authorize and block IP addresses for API and SMTP security" and its SMTP troubleshooting
page, read 2026-11-13; none of it was exercised on the account.

**Authorise the sending box's outbound address before any other address, or together with it, then send a test mail
from the box.** Authorising any address by hand starts blocking for API and SMTP calls alike, and SMTP addresses are
never learned, so a box that is not on the list stops sending. From a container the outbound address can differ
from the host's public one, which the test mail shows.

**Settings → Security → Authorized IPs** holds one list shared by API keys and SMTP keys, and a blocking switch for
each kind. Either switch can be turned on by hand. The API one also turns itself on: Brevo authorises each calling
address as it appears, with the /24 around it, and starts blocking once 30 days pass with no new address.

A refused SMTP send fails with `525 5.7.1 Unauthorized IP address`. A refused API call is reported to answer `401`
with a message about an unrecognised IP address (quoted in a third-party integration guide, not observed); the key
itself is fine. Moving the sending service to another box means authorising its address first.
