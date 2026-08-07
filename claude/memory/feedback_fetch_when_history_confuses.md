---
name: feedback_fetch_when_history_confuses
description: Run `git fetch` the moment anything about a repo's history is confusing — local refs look exhaustive but silently exclude unfetched remote commits
metadata:
  type: feedback
---

**Whenever something about a repo's history doesn't add up, run `git fetch` before theorising.**
Not just "does this file exist" — any confusion at all: work that seems missing, a deployment
ahead of the source, a commit referencing something absent, a feature nobody appears to have
written, a working tree that doesn't match what's running.

Local investigation *looks* exhaustive while being silently incomplete. `git log --all`,
`git branch -a`, `git stash list`, `git fsck --unreachable`, `git reflog` and a filesystem sweep
all consult **cached** refs. `origin/main` is a snapshot from the last fetch and can be days
stale, so every one of those commands can agree that something doesn't exist while it sits on
the remote.

**Why:** in travel-map, production was serving a whole password-gated visits feature — `crypto.js`,
an encrypt/decrypt module pair, a rewritten build script — that appeared in no branch, stash,
reflog, dangling object or anywhere on disk. I concluded it was lost, called the deployed bundle
"the only surviving copy", backed it up, launched a 5-angle forensic investigation into how it
vanished, and started planning a reconstruction. The user asked, "wait, isn't this feature pushed
to the repository yet?" — `git fetch` pulled 3 commits containing every single file. The last
fetch had been two days earlier. Everything downstream of that stale ref was wasted work built
on a false premise.

**How to apply:**
- Fetch *first*, as a reflex, when the question is about history — where something went, whether
  it was committed, why two things disagree. It costs a second.
- Until fetched, say "not in any **local** ref", never "doesn't exist anywhere".
- Treat a user's "wait, isn't it…?" as probably right: re-verify before defending the conclusion.
  Here it overturned the entire framing.
- Applies to a stale local checkout generally — before concluding a file is missing or a doc is
  wrong, confirm the checkout is current. Related: [[feedback_no_guessed_facts]].
