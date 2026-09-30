---
created: 2026-09-30 14:15:09
---

# Fold pick-session.py's dashboard-URL copy into peer_relay.dashboard_url

Three places resolved the local dashboard's base URL independently; two remain.

`claude/skills/shared/peer_relay.py` holds the canonical one, `dashboard_url()` — it reads `TAURI_DASHBOARD_URL` with `DEFAULT_DASHBOARD` as the fallback and strips a trailing slash. It was private (`_dashboard_url`) until `session_clean.py` was added on 2026-09-30 and needed the same value; promoting it to public was what kept that from becoming a third copy.

The remaining duplicate is in `claude/remote-session/mac/pick-session.py`, in the function that builds the `/api/agents` request: it inlines the same `os.environ.get(...).rstrip('/')` expression plus its own `DEFAULT_DASHBOARD` constant. So the env override and the default port live in two modules, and a change to either — a different variable name, a port move, a scheme change — lands in one and silently misses the other.

Why it was left: it sits in a different subtree from `skills/shared/`, and folding it in was outside the scope of the change that noticed it (adding the peer-pull clean signal), which would have made that commit describe work it did not contain.

What to do: import `dashboard_url` from `peer_relay` in `pick-session.py` and delete its local constant and expression, or — if the import across subtrees is unwanted — say in both files that the value is defined twice and why.
