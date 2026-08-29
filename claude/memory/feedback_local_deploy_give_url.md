---
name: feedback_local_deploy_give_url
description: When reporting that a site or app is running locally, always give the user the URL
metadata:
  type: feedback
---

When you report that a website, app or dev server is deployed or running locally, always include the URL the user can open. Give the full address — scheme, host, port, and the path that matters — never just "the server is running", and never a bare filesystem path in its place.

**Why:** Requested as a guideline on 2026-08-26. Observed in that same session: a local preview server was started on port 8731 to check a generated static site, and the user was never told the address — the write-up pointed at a filesystem path instead.

**How to apply:** Put the URL in the message where you report the deployment, in a form that can be clicked or copied. Where a script starts the server, make the script print the address rather than relying on the report to carry it: `deploy-dev-server.sh` ends a successful start with `open: http://localhost:<port>` (added 2026-08-28, at the user's request, after the rule was missed on the `deploy` path). That covers the `deploy` verb only — for a server started any other way, saying the address is still on you. Link the page the work was actually about, not only the site root — if the change lives on one page, give that page's URL. State explicitly whether the server is still up or has been stopped, since a URL for a killed server is worse than none. Pairs with [[feedback_ask_before_touching_servers]], which covers announcing starts and asking before stops; this adds that the announcement must carry the address.
