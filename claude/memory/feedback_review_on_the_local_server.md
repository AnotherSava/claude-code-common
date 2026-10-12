---
name: feedback_review_on_the_local_server
description: Hand over the running local server for review; never publish to production just so the user can look at a change
metadata:
  type: feedback
---

Hand over the running local server for review. Do not publish to production so the user can see something.

On 2026-10-12 the user asked, after seven publishes in a row made only so they could look at a change:
"why don't you spin up local deployment so that you don't have to push each time for me to review a
feature". The server had been running the whole time — `deploy` starts it and fronts it on the tailnet, and
the script prints the URL — and I kept sending them to the live site instead.

**Why:** a dev server serves the working tree and hot-reloads, so it shows uncommitted work the moment it
exists. Publishing in order to look at something couples review to commit, push, CI and a production deploy,
turns every round of feedback into a release, and puts half-reviewed work in front of the app's real users.

**How to apply:** after a change, run the project's own deploy script and hand over the URL the tailnet
helper prints, with the path the work is about appended. Commit and publish once the user says the work is
right, in batches rather than per edit. Where the local database is a copy synced from production, name that limit each time it matters:
records created on production since the last sync are absent from it, and a re-sync destroys anything
stated only on the local copy. Related: [[feedback_deploy_script_not_skill]],
[[feedback_deploy_publish_separate_verbs]].
