# Cloudflare Pages — static deploy via wrangler, subpaths, custom domains, token gotchas

Deploying a self-contained static bundle to Cloudflare Pages with `wrangler` **direct
upload** (no Git-connected build, no Workers). Good fit when the build runs locally and
you just want to publish a folder.

## Direct upload

```bash
# one-time: create the project
npx --yes wrangler pages project create <name> --production-branch <branch>
# each deploy: upload a built folder
npx --yes wrangler pages deploy <dir> --project-name <name> --branch <branch> --commit-dirty=true
```

`--branch <branch>` equal to the production branch makes it a production deploy.
`--commit-dirty=true` silences the "working directory has uncommitted changes" warning.
First deploy prints a `https://<hash>.<project>.pages.dev` URL; the project root is
`https://<project>.pages.dev`.

Auth: either `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` in the environment, or a
prior interactive `wrangler login`. Direct upload sidesteps the GitHub OAuth handshake
that Git-connected builds require (that handshake is **not** API-scriptable).

## Serving under a subpath (e.g. site.com/travel)

Pages maps the **contents** of the output directory onto `/`. To serve under a subpath,
nest the files in a same-named subfolder of the output dir, and add a root `_redirects`
for the apex:

```
dist/
  _redirects          # "/    /travel/    302"
  travel/             # -> site.com/travel/
    index.html ...
```

No Worker or route needed. Keep asset paths in `index.html` relative so they resolve
under the subpath.

## Custom domain via the REST API

Two steps — Pages does **not** auto-create the DNS record:

1. Register the domain on the project:
   `POST /accounts/{acct}/pages/projects/{proj}/domains` with `{"name":"site.com"}`.
2. Create a **proxied** apex CNAME → `<proj>.pages.dev`:
   `POST /zones/{zone}/dns_records` with
   `{"type":"CNAME","name":"site.com","content":"<proj>.pages.dev","proxied":true}`.
   (Cloudflare flattens CNAME-at-apex; the orange-cloud proxy is required for Pages.)

Domain status goes `initializing` → `pending` (CNAME detected) → `active` (cert issued,
a few minutes). The site often serves over HTTPS while still "pending".

## Token gotchas (these cost real debugging time)

- **Account-owned tokens have a `cfat_` prefix.** They **cannot** be verified at
  `/user/tokens/verify` — that returns `Invalid API Token (1000)` *even when the token is
  valid*. Verify account-owned tokens at `/accounts/{acct}/tokens/verify` instead. Don't
  conclude a token is dead from the `/user/...` endpoint.
- **DNS records need the DNS permission groups, not the Zone ones.** "Zone Read" / "Zone
  Write" govern zone *settings* and do **not** grant access to `.../dns_records` — using
  them returns `Authentication error (10000)` on both read and write. You need **DNS Read**
  (`82e64a83756745bbbb1c9c2701bf816b`) and **DNS Write**
  (`4755a26eedb94da69e1066d98aa820be`). For the apex CNAME the token needs Account →
  Cloudflare Pages → Edit **and** Zone → DNS → Edit.
- **Editing a token's permissions keeps its secret; "Roll" changes it.** If you add a
  scope by editing, the value in your `.env` stays valid. Don't roll unless you intend to
  replace the secret everywhere.
- **Listing zones needs Zone → Zone → Read.** A DNS-only token returns an empty zone list,
  so you can't discover the zone ID without it.
- Inspect a token's actual policies (permission groups + scoped resources) via the account
  tokens API to see exactly what it can do, rather than guessing from the dashboard.

## See also
- `mapbox-gl-js.md` — Mapbox token URL restrictions (the public token baked into such a
  static bundle should be locked to the deployed domain).
