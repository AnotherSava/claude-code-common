# Google OAuth for a personal account and a local script

Setting up an installed-app ("Desktop") OAuth client so a local script can call a Google API as the
user. Applies to any Google API — People, Gmail, Calendar, Drive. The API-specific parts live in their
own files (e.g. `google-people-api.md`, `gmail-api.md`).

There is **no API for creating OAuth client IDs** — not in the REST APIs, not in `gcloud`. That one
step is Console-only and cannot be scripted or done on the user's behalf. Everything after it can.

## The Console path

1. Enable the target API: `console.cloud.google.com/apis/library/<api>.googleapis.com`
2. Consent screen: `console.developers.google.com/auth/branding` — app name + support email. If it
   says "Google Auth platform not configured yet", click **Get Started**.
3. Audience: `console.developers.google.com/auth/audience` — see below.
4. Client: `console.developers.google.com/auth/clients` → **Create Client** → **Desktop app** →
   download JSON.

A correct Desktop client JSON has a top-level `installed` key and `redirect_uris: ["http://localhost"]`.
A `web` key or a service-account key means the wrong credential type was created.

## Internal vs External — the `org_internal` trap

Google's own quickstarts say to select **Internal**. That option only exists for projects owned by a
Google Workspace organisation, and it restricts consent to members of that org. A personal
`@gmail.com` account has no organisation and must use **External**.

The trap is that a Cloud project created while signed into a Workspace account inherits the org, so
Internal is offered *and is the default* — and then consent from a personal account dies with:

```
Access blocked: <app> can only be used within its organization
Error 403: org_internal
```

The error names the app, not the account, so it reads like a misconfigured client rather than an
audience mismatch. Fix: switch the audience to External. Or, if the data you want lives on the
Workspace account after all, keep Internal and consent with *that* account — Internal is strictly
better where it applies, because the 7-day rule below doesn't touch it.

If org policy forbids making apps External, the way out is a Cloud project created under **No
organization**, which means a new project and a new client JSON.

## Publishing status decides how long the refresh token lives

This is the setting that determines whether the script keeps working. Google's OAuth documentation
lists the conditions under which a refresh token expires, and one of them is:

> Testing publishing status + External user type → refresh tokens expire in 7 days

(the exception being requests for only `openid` / `userinfo.email` / `userinfo.profile`).

So a personal script left on the default *Testing* status stops working a week after setup, with an
`invalid_grant` that looks like a broken tool rather than an expired grant. Click **Publish app** to
move it to **In production**.

**Verification is a separate thing and is not required.** For sensitive scopes the Console shows "Your
app requires verification… submit your app for review" — that's a prompt, not a gate. An unverified
production app works; it shows a "Google hasn't verified this app" interstitial on first consent
(**Advanced → Go to \<app\>**) and is capped at 100 users. Verification wants a privacy policy, a
homepage on a verified domain and a demo video, and takes weeks — pointless for a one-user script.

One caveat worth carrying: Google's docs put the 7-day rule on *Testing*, but there are field reports
of production-but-unverified apps with sensitive scopes still expiring. Treat re-consent as cheap
rather than assuming it never happens.

The other expiry conditions apply regardless: unused for six months, user revoked access at
`myaccount.google.com/permissions`, password changed while holding Gmail scopes, or too many live
refresh tokens for the account.

## The flow, with `google-auth-oauthlib`

```python
from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
credentials = flow.run_local_server(port=0, prompt="consent")
credentials.refresh_token   # the durable value — store this, not the access token
```

`prompt="consent"` matters: without it Google returns **no refresh token** on re-authorisation, so a
re-run silently keeps whatever stale token you had. `port=0` picks a free port and the redirect URI is
matched by loopback rule, so the client's registered `http://localhost` covers any port.

For normal runs, rebuild credentials from the stored refresh token and let `AuthorizedSession` handle
refresh:

```python
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials

session = AuthorizedSession(Credentials(
    token=None, refresh_token=stored, client_id=..., client_secret=...,
    token_uri="https://oauth2.googleapis.com/token", scopes=SCOPES,
))
```

Store the refresh token by piping it into the secret store over **stdin** — never print it and never
pass it as a command-line argument, or it ends up in the terminal scrollback and shell history.

## Running the flow from a captured (non-tty) stdout

`run_local_server` opens the browser *first* and only then prints "Please visit this URL to authorize
this application: …". With stdout captured rather than attached to a terminal, Python block-buffers,
so the URL never appears — and if the browser didn't open (or opened in the wrong profile), there is
nothing to fall back to.

Set `PYTHONUNBUFFERED=1` so the URL lands in the captured output immediately. It's needed only when
something else is reading the process's stdout.

The URL cannot be reconstructed afterwards: it carries a `state` value and a PKCE `code_challenge`
generated inside that specific process, and the local server rejects a callback that doesn't match. A
hand-built URL is useless — capture the real one, or restart the flow.
