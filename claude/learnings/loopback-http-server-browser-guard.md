# Guarding an unauthenticated loopback HTTP server from the browser

A server bound to `127.0.0.1` with no authentication is reachable from every web page the user has open. The page usually cannot read the answer, but it can send the request, and a page whose domain is DNS-rebound to `127.0.0.1` can do both. The legitimate callers of such a server — hooks, curl, urllib, PowerShell's web cmdlets, Node's `fetch` — send no `Origin` header, and browsers do. That asymmetry is the whole guard, and each edge of it has a trap.

The browser rules below are from the WHATWG Fetch spec's "append a request `Origin` header" algorithm, read 2026-09-26. The server-side behaviour was verified with curl against a live axum 0.8 server, the one in tauri-dashboard's `http_server.rs` (`origin_blocked`, `csrf_refusal`). No exploit was run in a real browser.

## When a browser attaches `Origin`

| Request | `Origin` header |
|---|---|
| Any method other than `GET`/`HEAD`, same-origin or cross-origin | Present |
| Cross-origin request in CORS mode (default `fetch`, XHR) | Present |
| WebSocket or WebTransport handshake, same-origin included | Present |
| Same-origin `GET`/`HEAD` | Absent |
| Cross-origin no-cors `GET` (`<img>`, `<script>`) | Absent |

The value is `null` instead of the page's origin in cases the page controls. They include a sandboxed iframe without `allow-same-origin`, a `data:` or `file://` document, and any non-CORS-mode request other than `GET`/`HEAD` made under `referrerPolicy: "no-referrer"`, such as `fetch(url, {method: "POST", mode: "same-origin", referrerPolicy: "no-referrer"})`. The default referrer policy, `strict-origin-when-cross-origin`, produces it with no opt-in: a non-CORS-mode request other than `GET`/`HEAD` from an `https` page to an `http` URL carries `Origin: null`, and a plain form POST to `http://127.0.0.1` is one.

## Refuse every `Origin`, `null` included

Refuse any request that carries the header, whatever its value. An exemption for `null` looks harmless because `file://` pages send it, but an attacker sends `null` whenever it likes. A rebound page is same-origin with the server, so it can POST a JSON body with no preflight, and the recipe above makes that POST carry `Origin: null`. The exemption therefore admits exactly the request the check exists to stop. No tool-shaped caller needs it, and a `file://` page never could have read the reply anyway, since the server sends no CORS headers.

Do not allow the server's own loopback origin either. The server serves no pages, so the only client sending that value is one adding the header by hand. Make the `403` body say to send no `Origin` header instead, so that client fixes itself in one round trip. An agent sending `Origin: http://127.0.0.1:<port>` to look correct is a real, repeated case.

## Rebinding on `GET` needs a loopback `Host`

A rebound page's same-origin `GET` carries no `Origin`, so the `Origin` check cannot protect a `GET` route that returns anything worth reading. Require a loopback `Host` there: `127.0.0.0/8`, `::1` or `localhost`. The rebound request carries the attacker's hostname in `Host`, because that is the name the browser resolved.

The cost is that a caller reaching the server through a hostname alias that resolves to loopback is refused, so decide per route whether an alias is a supported setup. Before deciding, search every caller for the environment variable that sets the base URL, other repositories included. The caller that reads a route through an alias may live in a different repo and run on a different machine than the one you are checking.

## What already stops a plain cross-site write

A cross-site page cannot send `Content-Type: application/json` without a CORS preflight. A server that never answers `OPTIONS` with CORS headers fails that preflight, so the browser never sends the request. Without a preflight the page is limited to form and text content types, which a JSON extractor requiring `application/json` rejects (axum 0.8's `Json` answers `415`). Against an ordinary site, then, the `Origin` check is a backstop; its real job is rebinding, where the request is same-origin and none of this applies.

## Probing the guard

- A guard written inside the handler runs after the body extractor. A probe with an empty or wrong-shaped body gets `415`/`400`/`422` and never reaches the guard, so send a valid body, chosen to be harmless if admitted (an end event for a made-up id).
- A body sent with `curl -d` defaults to `application/x-www-form-urlencoded`. Add `-H 'Content-Type: application/json'`, or a JSON extractor answers `415`.
- Adding `-H 'Origin: null'` to that request exercises the `Origin` gate, and `-H 'Host: evil.example:<port>'` the `Host` gate, without a browser.
- The Fetch spec page is too large for a fetch-and-summarise tool, which reports the algorithm as absent. Download it with curl and extract the section by its anchor id, `append-a-request-origin-header`.
