---
created: 2026-11-22 11:16:54
---

# Reconcile what publish verifies for an app whose pages all need a session

The auth skill (claude/skills/auth/SKILL.md, step 2 item 2) tells an adopting app to point publish's verification at a public status-only health route, while publish-ssh-compose.sh's header (line 17) asks VERIFY_URL to be a real user-facing page, not a health endpoint, and check_url accepts only a 200. Once every page needs a session, no page can answer 200, so scheduler (2026-11-22) set VERIFY_URL=/api/health and its publish no longer proves pages render: a bad AUTH_SESSION_SECRET or a render error passes. Decide one rule and change both files to it. Options: let VERIFY_URL name an expected status (a gated page answering 302 to /auth/login proves the app and sign-in config load), or require a public page that renders through the app's layout. Then update the scheduler adoption to match.
