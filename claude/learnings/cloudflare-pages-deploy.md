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
First deploy prints a `https://<hash>.<project>.pages.dev` URL; the project root is
`https://<project>.pages.dev`.

### `--commit-dirty=true` hides a real trap

It silences the "working directory has uncommitted changes" warning — but wrangler still stamps
the deployment's metadata (`deployment_trigger.metadata.commit_hash` / `commit_message`) from
the **local git HEAD**, while uploading whatever bytes are in the folder. Publish a dirty tree
and the dashboard shows a deployment perfectly reconciled to a commit that does not describe
what is being served. Nothing surfaces the divergence; it only shows up if someone diffs the
live bundle against the repo, which can be weeks later.

Two consequences worth designing around:
- **Prefer publishing from CI**, which builds a clean checkout of one commit. That removes the
  whole class rather than guarding it, and also removes the sibling failure of a developer
  building with the wrong environment's secrets.
- If publishing locally anyway, **gate on a clean, pushed tree** rather than passing
  `--commit-dirty=true` reflexively, and pass `--commit-hash "$GITHUB_SHA"` (or the local rev)
  explicitly so the metadata is meaningful.

Related: a direct-upload project reports `"source": null` in the API, and *stays* direct-upload —
adding a GitHub Actions workflow that calls `wrangler pages deploy` does **not** convert it to a
Git-connected project, so the two approaches don't conflict.

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
  tokens API to see exactly what it can do, rather than guessing from the dashboard. Reading
  them needs **API Tokens Read**, which a working token normally does not carry — so the
  fallback is the token's Summary tab in the dashboard, which lists every policy and is worth
  asking for before inferring a permission from which probes pass.
- **A probe that succeeds names no permission.** An endpoint can answer 200 off a group you
  were not thinking about, so "the GET worked, therefore Read is granted" is not sound — and
  it leads to asking for Edit on a group the token does not carry at all. Verified on
  `…/email/routing/rules`, which read fine with no Email Routing permission anywhere.
- **Minting needs API Tokens Write**; without it `POST /accounts/{acct}/tokens` returns
  `403 9109 Unauthorized`. Probe with `"policies":[]` — an authorization refusal proves the
  limit while creating nothing, where a validation error would mean the create is allowed.
- **API Tokens Write also edits an existing token**, so a scoped setup permission need not be
  a permanent grant. `PUT /accounts/{acct}/tokens/{id}` takes the whole token — `{name, status,
  policies}` — so read it first, filter `permission_groups` by id, and PUT the result; the
  secret is unchanged, per the Roll bullet above. Keep the pre-edit JSON and diff the policies
  afterwards on `(id, resources, effect, group names)`: that is what distinguishes "removed the
  two groups I meant" from "rewrote the policy", and the response body alone does not.
- **A permission group can be listed on a token and still authorize nothing, because it is
  scoped to the wrong resource kind.** A group belonging to an account-level API — Pages,
  Workers KV, Workers Scripts — inside a policy whose `resources` key is
  `com.cloudflare.api.account.zone.<zoneid>` is accepted by the dashboard and refuses every
  account endpoint with `10000`. So the token's Summary tab reads as if the capability is
  there. Check the resource kind beside each group, not just the group list, and treat
  "listed but refused" as mis-scoping before suspecting the credential.

## See also
- `cloudflare-email-routing-inbound.md` — receiving mail on a zone, and the Email Routing
  permission groups, which are three different things with similar names.
- `mapbox-gl-js.md` — Mapbox token URL restrictions (the public token baked into such a
  static bundle should be locked to the deployed domain).
