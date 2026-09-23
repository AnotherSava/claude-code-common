---
title: Worker hostnames carry the project's name
rules: cotenant-hostnames
---

## What changed

A DNS zone is a shared namespace, and owning it is what makes that easy to miss. Version 008 covered
the two namespaces where the neighbours are obvious — a docker bridge, a flat `conf.d` — and a zone
behaves the same way with none of the warning signs: `anothersava.com` is the user's own, so a
project taking `notify` in it feels like naming a file rather than claiming something.

A Cloudflare Workers custom domain binds a hostname to exactly one Worker. The first project to
deploy `notify.example.com` holds it, and the second project's deploy is refused or silently points
the name at a different script. The Worker's own name is the same claim one layer up: script names
are account-wide, so `wrangler deploy` of a second Worker called `notify` replaces the first
project's deployed code rather than sitting beside it.

Nothing scarce is being conserved by sharing a name. A zone allows 100 custom domains and 1,000
routes, identical on the free and paid plans, and one Worker may carry several
(`learnings/cloudflare-workers-push-to-a-pulling-app.md`).

The shape this asks for is one name per project, twice over: a script name that no other project
would also pick, and a hostname whose leftmost label opens with that script name.

**This one detects and never edits.** A hostname is written into the Worker's config, into the app
that dials it, into whatever holds the secret that authenticates the connection, and into the DNS
record Cloudflare created for it. A rename that misses one of those does not error at the edit — it
fails later at a TLS handshake or a refused subscribe, far from its cause. So find the deviation,
name it, and put the edit to the user.

## Migrating an existing repo

There is a finding here when a `wrangler.toml` in this repo declares a script name inside the
generic set, a route whose leftmost label is inside that set, a route whose leftmost label does not
open with the script's own name, or a route claiming the zone apex or a wildcard. Name the file, the
line, the name it should carry and the rule it breaks, then put it to the user. Change no wrangler
file on their behalf.

Read the generic set from `claude/scripts/ingress-lint.py`, imported rather than copied so the
commit-time lint and this rule cannot disagree about what generic means, plus the function words the
rule adds for hostnames. Where the import fails, say so and refuse to judge rather than falling back
to a second copy of the list.

**A function word outside that set passes, and the rule says so rather than implying otherwise.**
The list is short because it is measured against the Workers this fleet actually deploys. So read
the hostnames yourself as well as running the rule: a label naming what the Worker *does* rather
than whose it is — `events`, `ingest`, `hooks` — is the same claim as `notify` even where nothing
flags it.

Four states are a question rather than a finding:

- **A wrangler file with no top-level `name`.** The script it deploys has no name to judge, and the
  hostnames below it have nothing to be checked against. Ask for the name rather than inferring one
  from the directory.
- **Wrangler config in a JSON or JSONC form.** The rule reads TOML and refuses the JSON forms by
  name, because a reader that skipped them would report a repo clean for the same reason an empty
  one is clean. Convert the file or extend the rule; do not let it pass unread.
- **A routes array this reader cannot take literally** — one spanning several lines, or a value
  built from a variable. The rule stops with the line printed verbatim. An unread array is a
  hostname claimed with nothing looking at it.
- **A wrangler file that cannot be opened at all.** Report it as the question, never folded into "no
  Worker here", which would turn an unreadable tenant into a repo that deploys nothing.

Afterwards:

- **Deploy the renamed Worker before deleting the old one**, and delete the old script explicitly —
  a rename in `wrangler.toml` deploys a *new* script and leaves the previous one running under its
  old name, still holding its custom domain. Nothing reports that; the old hostname goes on serving
  the old code.
- **Move the custom domain in Cloudflare, not only in the file.** The `[[routes]]` entry asks
  Cloudflare to create the record; changing the pattern does not remove the record the old one
  created, so the retired hostname keeps resolving to a Worker nobody maintains.
- Read the references no scan can see. The rule searches this repo's wrangler files and nothing
  else — the app's own config, a Doppler value, a runbook, or a secret's name can each carry the
  hostname. Grep the repo for the old name before calling the rename done.
- Check the certificate before trusting a new hostname. Free Universal SSL covers one subdomain
  level, so `project-notify.example.com` is covered while `notify.project.example.com` serves no
  valid certificate at all and fails the handshake outright. Flatten the name rather than buying
  Advanced Certificate Manager.

## When it does not apply

The repo holds no wrangler config. That absence is positive evidence that the repo deploys no Worker
today, so it claims no name in the account and none in the zone. Every repo on this machine but one
answered this way when this version was written, on 2026-09-23.

It is a fact that expires, which is why the rule runs at every commit rather than the reading
standing on its own: the first of those repos to deploy a Worker surfaces as a finding rather than a
silence.

## Continuing rule

`cotenant-hostnames` — every `wrangler.toml` in the repo declares a top-level `name` outside the
generic set, and every route it claims has a leftmost DNS label that opens with that name. A pattern
claiming the apex or a wildcard is reported on its own terms, because it is not a name that could be
prefixed but a claim on the whole zone, which is the collision rather than an instance of it. The
label assertion needs no word list: it forces the hostname to inherit whatever the script name is,
leaving one name per Worker to get right. Wrangler config in a JSON form, a claim the reader cannot
take literally, and a file that will not open are each raised rather than returned as clean, because
the checker prints an empty list as a rule that held.
