---
name: A check must distinguish "passed" from "could not run"
description: Verification that reports success when it did not actually run is worse than no check — it converts an open problem into a closed one
metadata:
  type: feedback
---

When writing or reviewing any check — a validator, a health probe, a lint, a test gate — make "it passed" and "it never ran" produce **different, visible** outcomes. A check that cannot tell them apart does not merely fail to help; it actively converts an unresolved problem into a resolved-looking one, and it does so exactly when something is already wrong.

**Why:** this shape recurs constantly and is invisible by construction, because the successful and the unexecuted paths print the same thing. Five instances from one week on one project:

- `caddy validate` exits 1 for an invalid config **and** for a stopped proxy. The first version of a fix deleted the tenant's working vhost and reported "restored the previous one", blaming a config that was fine.
- The stock caddy image ships a placeholder `/etc/caddy/Caddyfile`, so if the real one is not bind-mounted, `validate` returns **0** against a welcome page — a green check on a config that imports nothing.
- An identity checker silently dropped the manifest's `_not_yet_covered` hosts, so "all 3 hosts serve their own application" was true and covered three of five, reading as complete.
- A publish decided "did the vhost change" from a commit delta the reconcile had already advanced, so after any failure the retry computed "unchanged", installed nothing, and printed `PUBLISH OK`.
- A container-path check verified `/etc/caddy/conf.d` while the install wrote to a host path, so a wrong path passed every check and the verify URL answered 200 from the file that was already there.

**The inverse is just as bad, and it hides in the caller.** A checker can draw the distinction correctly and have it thrown away one line later: `identity-check.py` returns 2 for could-not-check and 1 for wrong-app, and its caller ran `... || { echo "this host may be serving another app"; }` — so a missing file, an expired token or a dead network all announced an impersonation, in the scariest available wording, moments after a proxy recreate had interrupted three sites. An operator starting an emergency rollback over a failed download would be responding rationally to the sentence they were shown. Both cases must still fail; only the wording may differ, because the wording is what drives the next action. Watch for this whenever a fetch replaces a local file — it widens the could-not-run surface at exactly the moment the message matters.

**Check runnability early, correctness late.** The same check placed dead-last fails after the build, the deploy and the recreate — loud, but only after every irreversible step. Hoist the "can this run at all" half to a preflight before the risky work and leave the verdict where it belongs, then classify identically in both places, or the preflight waves through the case the final check condemns.

**How to apply:** probe the precondition separately rather than inferring it from the exit code (is the service running; is the real file mounted; does the artifact exist where the check looks). Assert the **property on the artifact**, not the provenance of the operation that produced it. When something is declared-but-unchecked, print it — `NOT COVERED` next to the reasons — and say so in the summary line rather than reporting a bare total. And prefer failing before writing over writing and reverting: a failure that never touched anything needs no restore to go wrong. See [[feedback_loud_errors]] and [[feedback_no_defensive_fallbacks]] — the same instinct at different layers.
