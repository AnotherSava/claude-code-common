---
name: auth
description: >-
  Give a web app real sign-in through the shared sign-in service.
  TRIGGER when: replacing an edge password, stubbed user or environment password with real sign-in;
  sign-in fails in an app with the module; `module/signin.ts` is changed or re-installed; or someone
  asks how a person is admitted to or removed from an app.
  DO NOT TRIGGER when: operating the sign-in service itself, token auth for a device or API client, or
  OAuth against a third-party API.
allowed-tools: Bash, Read, Edit, Write, Glob, Grep, AskUserQuestion, Skill
---

# Sign-in for an app

An adopting app becomes an OpenID Connect client of the shared sign-in service. A person proves who they
are there, with a passkey or an emailed code, and comes back with a session cookie the app issued itself.
The service decides *who may enter* (one group per app); the app decides *what they may do*.

Three things hold the pieces, and each fact has one home:

- **The `auth` repo**, private, checked out beside the project: the service, and `docs/app-contract.md`,
  the page that states the service's address, the client settings, the claims and the registration
  credential. This skill repeats none of it, apart from two names its registration script needs: the
  group it creates is named after the app's compose project, and the key it reads is
  `AUTH_ADMIN_API_KEY`.
- **This skill**: the method below, `module/signin.ts` with its three route files, `scripts/e2e.mjs`
  and `scripts/register-app.mjs`, and the recipes for an app's data under `references/`.
- **The app**: an unchanged copy of the module, and its own single function that turns a session into
  that app's user.

## Context

- Contract page: !`test -f ../auth/docs/app-contract.md && echo PRESENT || echo MISSING`
- Module under web/: !`test -f web/src/lib/signin.ts && echo installed || echo absent`
- Module at the repo root: !`test -f src/lib/signin.ts && echo installed || echo absent`

## 1. Read the contract

1. If **Contract page** is `MISSING`, stop. Say that the `auth` repo has to be checked out in the same
   parent folder as this project, and take no fact about the service from anywhere else.
2. Read `../auth/docs/app-contract.md` whole. "The contract" below means that page.
3. Where the contract marks something as not yet measured, stop before the step that depends on it and
   say which one.
4. If a **Module** line reads `installed`, compare it with this skill's copy before anything else, with
   the app's path in place of `<app>`:

   ```bash
   cmp ~/.claude/skills/auth/module/signin.ts <app>/src/lib/signin.ts && echo current
   ```

   Anything but `current` means the app runs code the end-to-end test never saw: re-install as
   **Install the module** describes.

`<app>` is the directory holding the Next.js app's `src/`, usually `web`.

## 2. Settle what stays public

1. List what the app serves without any credential today: the vhost's carve-outs, what `proxy.ts` lets
   through, feeds whose token is in the path, the identity route, and any route that takes a write from
   anyone (an order form, a webhook).
2. List what calls the app with no person behind it: the container's healthcheck, which reaches the app
   directly and so never met the vhost's password, and each URL the project's publish verification
   expects a 200 from. In the gated shape a gated path answers both with a 401, or with a 302 to sign-in
   when the request asks for HTML, so the container never turns healthy and the publish fails its check.
   Give each a public path to call: a route already on the list, or a health route added to it whose
   body says only whether the app is up, with no error text and no data.
3. Ask the user, in one question that shows the list, which of two shapes the app takes:
   - **gated**: every request needs a session, except a GET of a path on the list;
   - **open**: pages stay readable by anyone and a session adds identity.
4. Never widen. A path that needs a password today is not public after adoption, whatever the list says.
   The status-only health route of item 2 is the one addition.

## 3. Settle whose data it is

Sign-in tells the app who is asking. Whether that changes what the person sees is a decision about the
app's data, and it is made here, before any code. An adoption that skips it ends with every signed-in
person reading and changing the same records, and nothing reports it.

1. List every kind of record the app keeps, from its schema, each with the column that ties it to a
   person where one exists. Add what lives outside the database or once per deployment: uploaded files,
   settings, a login for an outside service in the environment, a token that opens a feed.
2. Find how the code names the current person today: not at all, through a stand-in (a stub the code
   looks up, or a row the seed creates), or through real accounts. Count the user rows.
3. Settle these with the user in one question that shows the list, with your recommendation on every
   row:
   - **who will be admitted**: the owner alone, people who share everything, or people who each keep
     records of their own;
   - **each kind of record**: shared by everyone admitted, or one person's;
   - **who inherits** what exists today, where records are one person's: the owner, unless the user
     names someone else;
   - **who may change the shared records and open the admin pages**, where that is not everyone;
   - **whose records the public pages show**, where the app is the open shape and its public pages show
     a person's records, and someone besides the owner will be admitted: the owner's alone, or each
     person's on pages of their own;
   - **each per-deployment item**: it stays the owner's, or everyone admitted acts through it.
4. Take the recipe the answers lead to, and read it whole before wiring:
   - `references/data-shared.md` where no record carries a user column, every kind stays shared, and
     everyone admitted may change the shared records;
   - `references/data-stand-in-user.md` where records carry a user column that a stand-in fills and the
     user table holds that stand-in alone, however many people will be admitted;
   - `references/data-public-view.md` as well, where the app is the open shape and its public pages show
     the owner's records alone.
5. Stop where no recipe fits, which is every case item 4 does not name. Those met so far: records that
   should become one person's and carry no user column; a user table holding any row besides the
   stand-in, where which row is which person at the sign-in service is settled by hand; people who
   should differ in what they may do in an app with no user table to hold a role; public pages of
   their own for people besides the owner, where a page takes the person it shows from a handle in its
   route; and a per-deployment item that should become each person's own. Say which, and settle the
   design with the user before going on. Afterwards, route what was built to the session that owns
   this skill, as a new recipe.
   A recipe never turns a case away itself: it sends one that stops fitting back to this step, so a
   new stop is written here and nowhere else.

## 4. Install the module

Run from the project root:

```bash
npm --prefix <app> install openid-client@6
mkdir -p <app>/src/lib <app>/src/app/auth/login <app>/src/app/auth/callback <app>/src/app/auth/logout
cp ~/.claude/skills/auth/module/signin.ts <app>/src/lib/signin.ts
cp ~/.claude/skills/auth/module/routes/login/route.ts <app>/src/app/auth/login/route.ts
cp ~/.claude/skills/auth/module/routes/callback/route.ts <app>/src/app/auth/callback/route.ts
cp ~/.claude/skills/auth/module/routes/logout/route.ts <app>/src/app/auth/logout/route.ts
```

Never edit an installed file. A change to the module is made in this skill, tested, and installed again
(see **Changing the module**). The route files import `@/lib/signin`; an app without that alias gets a
relative import in its three copies and nothing else changed.

## 5. Wire the app

1. **The gate.** Put it first in `<app>/src/proxy.ts`, ahead of whatever that file already does. A string
   matches a whole path; a RegExp tests it. For the gated shape, pass the public list settled in
   **Settle what stays public**:

   ```ts
   import type { NextRequest } from "next/server";

   import { gate } from "@/lib/signin";

   const PUBLIC_PATHS = ["/api/identity", /^\/feed\/[^/]+\/calendar\.ics$/];

   export function proxy(request: NextRequest): Response | undefined {
     return gate(request, PUBLIC_PATHS) ?? undefined;
   }

   export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };
   ```

   For the open shape, pass a pattern for every path outside the sections that need a session. A read
   stays open and a write still needs a session, since Next forwards a server action posted to any
   page:

   ```ts
   const PRIVATE_SECTIONS = ["admin"];
   const PUBLIC_PATHS = [new RegExp(`^/(?!(?:${PRIVATE_SECTIONS.join("|")})(?:/|$))`)];
   ```

   A route that takes a write from anyone, or that authenticates another way (a device presenting its
   own token), carries no session. Return early for its prefix before calling the gate, and leave its
   own check in place. The pages of an open app ask `readSession` and render for whoever they find.
   On an open app only a page in a private section sends a signed-out person to sign in, so a person
   signs in by opening one of those pages or `/auth/login` itself; a link that offers a way in points
   at `/auth/login?next=<the current path>`.
2. **One function that names the app's user.** Keep or create a single function (`getCurrentUser`,
   `requireSession`) that every caller goes through, built on:

   ```ts
   import { headers } from "next/headers";

   import { readSession } from "@/lib/signin";

   const session = readSession((await headers()).get("cookie"));
   ```

   - The recipe taken in **Settle whose data it is** gives the function's body. Where the app keeps a
     row per person, key it on `session.sub`, which never changes; the address and the name are
     attributes.
   - A session says the service vouched for this person when the cookie was issued. What they may do,
     and whether they still may, is read from the app's own data on each request.
3. **The data.** Carry out that recipe in the same change set as the wiring: its schema change, its
   hand-over of the records that exist today, its tests, and the decision written into the app's docs.
4. **Every server action and route handler that reads or changes non-public data calls that function
   itself.** The gate is the outer check only: a `matcher` can exclude the path an action runs on, and
   Next forwards a server action posted to any page (`~/.claude/learnings/nextjs-server-actions-path-gating.md`).
   Enumerate them (`'use server'`, `route.ts`) and check each one; do not sample.
5. **A sign-out control**, a plain form, wherever the app shows who is signed in:

   ```tsx
   <form action="/auth/logout" method="post"><button type="submit">Sign out</button></form>
   ```

6. **Remove what sign-in replaces**, in the same change: the password page and its action, the
   environment password, the stubbed user. Before deleting the page, search the app for every path that
   leads to it (a `redirect`, a `window.location` assignment, a link, a `next` built for it) and point
   each at `/auth/login?next=<the path to come back to>`. A build accepts any string as a path, so a
   reference left behind shows only as a 404, the first time the person is signed out.

## 6. Run it in development

Development signs in without the service. In the app's development environment only, set:

```
AUTH_DEV_USER=<an address>
AUTH_ORIGIN=<the address the dev server is opened at>
```

That address is the `open:` line the dev deploy prints: its tailnet URL, or `http://localhost:<the dev
port>` where the project sets `DEV_TAILNET=no`. A page opened at any other address has its sign-out
refused with 403, and `/auth/login` sends it to AUTH_ORIGIN. A tailnet URL names one machine, so each
machine that runs the dev server sets its own, outside anything both machines read.

Every request is then that person, with `sub` `dev:<address>`. The module throws if `AUTH_DEV_USER` is set
in production. Run the project's real gate (its build, then its tests), start the dev server, and load a
page that needs a session.

To sign in against the real service from a dev server instead, add `<AUTH_ORIGIN>/auth/callback` to the
callbacks when registering, one for each machine's AUTH_ORIGIN, and give the development config every
variable **Register the app with the service** sets.

## 7. Register the app with the service

This writes to the service and to the app's secret store. Show the user the values below and get their
go-ahead first.

1. Read the issuer from the contract and confirm the service answers:
   `curl -s <issuer>/.well-known/openid-configuration` must contain the issuer. If it does not, stop:
   everything up to the development run stands on its own, and registration waits for the service.
2. Collect the values:
   - project: the app's compose project name;
   - name: what a person should see for the app;
   - callback: `https://<app host>/auth/callback`; logout callback: `https://<app host>/`, with the host
     from the app's vhost;
   - the app's Doppler project and config, from `DOPPLER_PROJECT` and `DOPPLER_CONFIG` in
     `config/publish.env` (print those two keys only).
3. Invoke `/doppler`, then register. The contract's section on creating a client says where the admin API
   key is kept; it is stored under the name the script reads, `AUTH_ADMIN_API_KEY`. The client secret goes
   from the script's stdout into Doppler and is never printed:

   ```bash
   S=$(doppler run --only-secrets AUTH_ADMIN_API_KEY -p <key project> -c <key config> -- node ~/.claude/skills/auth/scripts/register-app.mjs --issuer <issuer> --project <project> --name "<name>" --callback <callback> --logout-callback <logout callback>) && [ -n "$S" ] && printf '%s' "$S" | doppler secrets set AUTH_CLIENT_SECRET -p <app project> -c <app config> --silent && echo "stored AUTH_CLIENT_SECRET, ${#S} chars"; unset S
   ```

   The script creates the app's group, creates the client restricted to it, and adds the key's owner to
   the group. It refuses a client that already exists; a further secret is then minted as the contract
   describes.
4. Generate the session secret straight into Doppler:

   ```bash
   openssl rand -base64 48 | tr -d '\n' | doppler secrets set AUTH_SESSION_SECRET -p <app project> -c <app config> --silent
   ```

5. Put the three values that are not secret where the app keeps its other settings, normally the compose
   file's `environment:`: `AUTH_ISSUER` (the issuer), `AUTH_CLIENT_ID` (the project) and `AUTH_ORIGIN`
   (`https://<app host>`).

## 8. Change the vhost

1. Delete `basic_auth` and the matcher that feeds it. The app asks for sign-in itself now.
2. Keep every tailnet gate and the `Next-Action` rule. They restrict where a write may come from; sign-in
   says who is making it.
3. Move what the deleted comments explained about each carve-out to the public list in `proxy.ts`.
4. Run the project's vhost lint.

## 9. Prove it

Publishing is the user's to ask for by name. Around it:

1. **Before the first publish with sign-in**, confirm the app's container reaches the service, which the
   token exchange needs. It reads production, so ask the user first:

   ```bash
   ssh <host> "docker exec <app container> node -e \"fetch('<issuer>/.well-known/openid-configuration').then(r=>console.log(r.status)).catch(e=>console.log('ERR',e.cause?.code??e.message))\""
   ```

   Keep the outer quotes: ssh joins its arguments into one line that the box's shell parses again, and
   without them that shell meets the script's parentheses bare and stops on a syntax error before
   `docker` runs. A syntax error is a quoting fault here, not an answer about reachability.

   Anything but `200` stops the adoption: say what it printed, and route it to the `auth` repo's session.
2. **After the publish**, from off the tailnet (pin the public address as
   `~/.claude/learnings/tailscale-docker-caddy-gating.md` describes, or every probe arrives on-net):
   - a gated page, requested as a page, answers 302 to `/auth/login`, which answers 302 to the issuer's
     authorization endpoint;
   - each public path answers 200 with no cookie;
   - a POST to a public path with no cookie answers 401.
3. **A real sign-in is the user's click**: ask them to open a page that needs a session (on an open app,
   a page in a private section or `/auth/login`), sign in, and sign out again. Signing
   out must return to the app's home page, and the next visit must ask for proof again. Where the recipe
   handed today's records to the person signing in, they must find those records there; nobody else is
   admitted before this sign-in.
4. Report what was observed for each check in this step, and which were not made.

## Admitting or removing a person

Both are the service's procedures, in `../auth/docs/operations.md`: a person enters an app by being put in
that app's group, and leaves by being taken out or disabled. Read that page; do not improvise the calls.

Before admitting anyone, read the **Who sees what** section in the app's docs. Admission gives the person
whatever that section says a person admitted gets, which in an app whose data is shared is all of it.
When that is more than this person should have, run **Settle whose data it is** again first. An app with
no such section was adopted before the decision existed: settle it now.

Removing a person stops new sign-ins at once. A session the app already issued lasts until it expires,
up to 30 days. To end every session of one app immediately, replace its `AUTH_SESSION_SECRET`, generated
as **Register the app with the service** shows, and publish; everyone signs in again.

## Changing the module

1. Resolve the symlink and edit the copy in the dotfiles repo: `claude/skills/auth/module/signin.ts`.
2. Run the end-to-end test. It needs Docker and Node 24, starts a throwaway Pocket ID from the image the
   `auth` repo pins, and must end with `0 failed`:

   ```bash
   node ~/.claude/skills/auth/scripts/e2e.mjs
   ```

3. Break the thing you changed and run it again. A check that stays green proves nothing about the change.
4. Re-install into each app that has the module, as **Install the module** describes, through that app's
   own session.

## Out of scope

- Do NOT write the service's address, a hostname, a group or a credential's location into this skill. The
  dotfiles repo is public; those facts live in the `auth` repo.
- Do NOT operate the sign-in service from here: its settings, upgrades, backups and recovery are its own
  repo's.
- Do NOT edit an installed copy of the module or its route files.
- Do NOT add self-signup, a password, or a second way in. An app that needs one is not adopting this.
- Do NOT add a user column, a role, storage per person or a public page per person that **Settle whose
  data it is** did not decide. A case no recipe covers stops at that step's last item.
- Do NOT publish. Adoption ends at a change set the user publishes by name.
