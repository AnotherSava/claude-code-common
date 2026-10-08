---
name: Reproduce infrastructure behaviour locally before asking to touch production
description: Behaviour determined by a versioned binary and a topology you can recreate is measurable on this machine; ask for a production action only once local reproduction is ruled out
metadata:
  type: feedback
---

Before asking the user to approve a disruptive action on a live system in order to **measure** something — restarting a container, killing an upstream mid-request, filling a disk — check whether the behaviour is a property of a versioned binary plus a topology you can stand up here. Where it is, install that same version, recreate the two or three moving parts, and measure locally. Reserve the production ask for what is genuinely specific to that deployment.

**Why:** the ask costs a round trip and costs the user a decision about their own running site, and the answer it buys is usually worse than the local one. Measured 2026-10-08: a claim that Caddy's `lb_try_duration` cannot protect a response already streaming sat labelled unmeasured in a learning, and the plan put to the user was to stream from the live site and restart the app mid-response. A local Caddy of the version the box runs, in front of a thirty-line throwaway upstream, answered it in one run — HTTP 200 with 26624 of 100000 bytes, against 28672 with the directive removed — interrupting nothing, and afforded a control the production version could not have. A second session had stopped at the same boundary for the same reason, so the same unnecessary ask was about to be made twice.

**How to apply:**
- Check the local binary's version against the deployed one and state it; a measurement from a different version answers a different question. Where the versions cannot be matched, say that rather than quietly measuring the wrong one.
- Recreate the smallest topology that shows the behaviour rather than the application. An upstream that writes slowly, or that accepts and then drops, is a dozen lines and is the thing under test.
- Include the control — the same measurement with the setting removed. That is what separates "this setting does nothing here" from "something else in the path did it", and a production run rarely affords one. A control that agrees with the test case means the harness is broken; see [[feedback_not_run_is_not_pass]].
- Take the throwaway servers' ports from the registry and release them afterwards (the `ports` skill), so a probe leaves no claim behind.
- This does not reach behaviour only the real deployment has — a reporter's environment, a race under real load, data you do not hold. [[feedback_branch_for_external_validation]] is that case, so say which of the two you are in instead of assuming local reproduction is always available.
