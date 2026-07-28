---
name: feedback_no_guessed_facts
description: don't state a guessed URL/path/endpoint/flag as known — verify it or say you're guessing
metadata:
  type: feedback
---

Don't fabricate a plausible-looking identifier — a URL, file path, API endpoint, config flag, filename — and present it as if known. Either verify it (grep the repo, read the docs, navigate to a page you can confirm) or state explicitly that you're inferring and ask.

**Why:** presenting a guess as fact burns the user's trust and time. A made-up `treatstock.com/3d-printing` quote-page path got denied, and the user had to challenge "is it in your guideline?" — the guess had no basis anywhere.

**How to apply:** before emitting a specific identifier, ask "do I actually have this recorded, or am I inferring it?" If inferring, flag it or confirm first. For a site path specifically, navigate to the site root and read the page to find the real route rather than guessing a subpath.
