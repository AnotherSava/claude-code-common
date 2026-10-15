# Next.js server actions and an edge that gates by path

A reverse proxy, WAF or edge rule that restricts writes by path — tailnet-only, IP-allowlisted, rate-limited — and
a Next app with server actions disagree about where a write happens. They disagree in both directions: giving a
page an action makes the whole page a write path, and gating a page's path does not gate its actions.

## An action's write surface is the page's URL

A server action POSTs to the URL of the page that rendered it. So an edge rule restricting write paths catches the
whole page the moment it grows an action, reads included. There is no path to carve out, because the action has no
path of its own.

Measured 2026-10-11: a booking detail page gained one inline action to store a coordinate, and the project's
ingress linter demanded `/bookings/*` join the matcher that answers 404 from off the tailnet — which would have
made a page read at a hotel desk unreachable from the internet. Moving the write to `POST /api/places` put one
path in the matcher and left the page readable.

Two consequences worth designing for:

- **Decide this before writing the action.** The two forms are a few lines apart in code and a long way apart in
  reachability, and nothing in the framework warns you.
- **The client then owns the failure message.** A `fetch` to a path the edge refuses answers with a status whose
  body is not your JSON, so trust the body only when it has the shape your handler returns and fall back to the
  status — otherwise a refused write reads as nothing happening.

## Gating a page's path does not gate its actions

Next 16's action handler (`next/dist/server/app-render/action-handler.js`) takes any POST carrying a `Next-Action`
header. When the action is not registered for the page it was posted to, `selectWorkerForForwarding` finds the
worker that owns it and `createForwardedActionResponse` re-issues the request to that worker's path from inside the
server. So an action defined on a tailnet-only `/admin/...` page can be invoked by POSTing its id to an ungated
page, and the edge never sees the gated path.

Exercised on 2026-10-14 against a 16.3.1 dev server: `POST /` carrying a settings page's action id was logged as
`POST /`, then `POST /admin/settings … <inline action>`, and the action ran. The re-issued request goes to
`__NEXT_PRIVATE_ORIGIN`, which `start-server.js` sets to the server's own `http://<hostname>:<port>`, so behind a
reverse proxy it never passes back through the proxy at all.

The hole has two limits, from the same source:

- **Only the header form is forwarded.** A no-JS form POST carries the action id in a `$ACTION_ID_<id>` body field
  and no header; it is resolved only against the page it was posted to and fails with "Failed to find Server
  Action" anywhere else. Path gating still governs that form, so the page holding an action must stay gated.
- **Only page renders forward.** The handler is reached from `app-render`; a header-bearing POST to a `route.ts`
  URL is not forwarded.

## Closing it at the edge

Add one rule that matches the header on every path and refuses it from off the gated network — in Caddy, a named
matcher of `header Next-Action *` plus `not remote_ip <ranges>`, answered with `respond @name 404`. It covers every
present and future action without listing any. An action id is not a secret worth relying on; without such an
edge rule, an action whose effect matters off the gated network needs its own check inside it, or belongs in a
route handler on a gated path.

Testing the rule from a laptop on the tailnet has its own trap, covered in `tailscale-docker-caddy-gating.md`: pin
the public IP, or every probe arrives on-net.
