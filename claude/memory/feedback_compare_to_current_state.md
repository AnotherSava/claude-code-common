---
name: feedback-compare-to-current-state
description: Evaluate downsides of a change against what ships today, not an idealized baseline; separate regressions from unchanged and improved
metadata:
  type: feedback
---

When asked about the downsides, risks, or trade-offs of a proposed change, anchor the comparison to **what is in place today**, not to an idealized baseline. State explicitly which items are genuine regressions and which are already true or actually improvements.

**Why:** asked for the downsides of shipping a Homebrew tap with a quarantine strip, I listed "the sha256 becomes the only integrity check" and "TCC/firewall grants reset on every version" as costs. Against the real baseline both were wrong — the existing DMG flow verifies no checksum at all and already instructs users to override Gatekeeper, and the grant churn comes from ad-hoc signing regardless of install method. The user had to redirect with "i meant downsides compared to current shipping." Measuring against a clean-slate ideal inflates the apparent cost of a change and misrepresents the decision being made.

**How to apply:** before listing drawbacks, name the current state explicitly and evaluate each item against it. Sort into "this gets worse", "this is unchanged", and "this improves" rather than presenting one undifferentiated list of concerns. The same applies to security arguments — a protection the status quo already forfeits is not a cost of the new approach.

Related: [[feedback_no_negative_from_partial_probe]], [[feedback_verify_symptom_not_proxy]]
