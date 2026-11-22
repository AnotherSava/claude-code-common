# Pocket ID API keys: minting one from a script

Read in Pocket ID v2.19.2's source (`backend/internal/apikey`, `onetimeaccess`, `webauthn`,
`cmds/one_time_access_token.go`) on 2026-11-22, and exercised once against a live instance.

## Minting a key needs a session

Creating a key (`POST /api/api-keys`) requires a browser session (`authz.AccountAPIKeysCreate`); an `X-API-Key` header is
refused. A script that needs a key therefore signs a person in first. With shell access to the container
there is a route with no passkey or mail:

1. Run `docker exec -u <service uid> <container> /app/pocket-id one-time-access-token <username-or-email>`; it
   prints `Use the following URL to sign in once: <APP_URL>/lc/<token>`. The token lives one hour.
2. A `POST /api/one-time-access-token/<token>` with no body answers 200 and sets the session cookie.
3. A `POST /api/api-keys` with that cookie and `{"name", "expiresAt"}` (name 3 to 50 characters,
   `expiresAt` ISO 8601 in the future) answers 201 with `{"apiKey": {...,"expiresAt"}, "token"}`. The
   token is 32 alphanumerics and is returned only once; the database keeps its SHA-256.

An admin's API key, or `STATIC_API_KEY`, replaces step 1 over HTTP alone, with no shell: the route
`POST /api/users/<id>/one-time-access-token`, sent `{"ttl": "15m"}`, accepts an API key and returns the
token for steps 2 and 3. Any admin key can therefore get a session, and so a key, for any user. The auth
skill's `scripts/e2e.mjs` takes this route.

Listing (`GET /api/api-keys`, `pagination[limit]` up to 100) and revoking (`DELETE /api/api-keys/<id>`,
204) accept the session too. The profile route `GET /api/users/me` accepts an API key and returns `id`, `username` and
`isAdmin`, which makes it the check that a stored key works and belongs to the right person.

## Lifetime and renewal

- No maximum expiry is enforced; any future date is accepted.
- The renew route `POST /api/api-keys/<id>/renew` works only on a key that has **already expired**, needs a session, and
  issues a new token. Rotating before expiry means minting a new key and revoking the old one.
- The name is not unique per user in the schema (only the hashed key is indexed unique).

## Expiry warning mail

A daily job at midnight mails a key's owner 7 days before it expires, but only when
`EMAIL_API_KEY_EXPIRATION_ENABLED` is `true`; the default is `false`. With `UI_CONFIG_DISABLED` the
setting comes only from the environment, so turning it on is a compose change and a redeploy.

## Signing out does not end the session

The logout route `POST /api/webauthn/logout` only answers with an expired cookie (always 204). The session JWT stays valid
on the server until `SESSION_DURATION` runs out, so a script holding the cookie in memory gains nothing
by calling it.
