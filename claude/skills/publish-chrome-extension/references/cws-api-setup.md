# Chrome Web Store API — one-time OAuth setup

The Web Store API uses OAuth2 with a refresh token tied to the **publisher's Google account**.
Everything below happens once per machine/account; afterwards `cws.sh` mints short-lived access
tokens automatically.

Canonical upstream walkthrough (with screenshots): the
[fregante guide](https://github.com/fregante/chrome-webstore-upload/blob/main/How%20to%20generate%20Google%20API%20keys.md).
The steps below are the condensed version wired to this skill's helper script.

## 1. Create the OAuth client

All steps in [console.cloud.google.com](https://console.cloud.google.com), logged into the same
Google account that owns the Chrome Web Store developer dashboard:

1. Create (or pick) a project — any name, e.g. `cws-publish`.
2. **APIs & Services → Library** → search "Chrome Web Store API" → **Enable**.
3. **APIs & Services → OAuth consent screen**:
   - User type **External**, fill in the app name and your email.
   - Add your own Google account as a **test user**.
   - **Important**: while the app's publishing status is *Testing*, Google expires refresh tokens
     after **7 days**. Push the app to **In production** (no verification is needed for the
     `chromewebstore` scope) to get a non-expiring refresh token. The auth page will then show an
     "unverified app" warning — click *Advanced → Go to … (unsafe)* to proceed; it's your own app.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type **Desktop app**.
   - Copy the **Client ID** and **Client secret**.

## 2. Wire the credentials into the skill

```bash
bash ~/.claude/skills/publish-chrome-extension/scripts/cws.sh init <client_id> <client_secret>
bash ~/.claude/skills/publish-chrome-extension/scripts/cws.sh auth
```

`auth` prints an authorization URL. Open it in a browser logged into the publisher account,
approve, and you'll be redirected to `http://localhost:8818/?code=...` — the page fails to load
(nothing listens there), which is expected. Copy the `code` query parameter from the address bar.
URL-decode it if needed (`%2F` → `/`); authorization codes expire within minutes.

```bash
bash ~/.claude/skills/publish-chrome-extension/scripts/cws.sh exchange <code>
```

This stores `REFRESH_TOKEN` in `~/.claude/skills/publish-chrome-extension/config/cws.conf`
alongside the client credentials. The config directory is gitignored in the dotfiles repo —
never commit it.

## 3. Recovery

- **"Failed to obtain an access token"** — the refresh token expired (Testing-mode app, see
  step 1.3) or was revoked. Re-run `auth` + `exchange`; `init` is not needed again.
- **HTTP 400 on exchange** — the authorization code expired or was pasted URL-encoded.
  Re-run `auth` and move quickly.

## API quirks

- Upload responses carry `uploadState`: `SUCCESS`, `IN_PROGRESS` (server still processing — safe
  to continue), or `FAILURE` with an `itemError` array explaining the rejection (e.g. version not
  greater than the published one, manifest errors).
- Publish responses carry a `status` array: `OK` means submitted; `ITEM_PENDING_REVIEW` means a
  previous submission is still in review — cancel it in the dashboard first or wait.
- The API cannot create new items or edit listing content — package upload + publish only.
- Publish can fail with HTTP 400 "Publish condition not met … Privacy practices tab" — typically
  when the new package adds permissions that need justifications. The user must fill those in on
  the dashboard's Privacy practices tab (API can't); the uploaded draft survives, so re-running
  `cws.sh publish` afterwards completes the submission.
