---
name: feedback_exempt_the_safe_value
description: A conditional gating a mandatory step enumerates the values it exempts, never the values it fires on, so an absent or unrecognised value still takes the step
metadata:
  type: feedback
---

A conditional that decides whether a **mandatory** step applies enumerates the values it *exempts*, never the values it fires on. An absent or unrecognised value then lands on the side that performs the step, which is the only direction that is safe to be wrong in.

Measured 2026-10-09 in the `wrap-up` skill's step 8. Its offer to run a deploy carried the machine-takeover ask that CLAUDE.md requires where **deploy type** was `tauri` or `intellij-plugin`, and exempted `dev-server`. Of the projects on this machine with a configured deploy, every one that declares a type declares `dev-server`, and the only one whose deploy raises a window — `tauri-dashboard` — carries no `DEPLOY_TYPE` key at all, so it reads `unknown`, matched neither listed type, and would have had its window raised with no ask. Every project that did match the exemption was correctly exempt, so the enumeration was right about every case it covered and wrong about the only one that mattered.

**Why:** enumerating the triggering values makes the default "skip the step", and the default is what an unconfigured, misspelled, renamed or newly-added value gets. Such a list is also written by someone reading the values that happen to exist that day, so it cannot cover the one added next month — while an exemption list stays correct as values are added, because a new value is unknown and unknown takes the step.

**How to apply:** write the condition as "everything other than `<safe value>`", and give the clause that says why that one value is exempt, so a later reader can audit the exemption instead of the obligation. Where no value is safe enough to exempt, the step is unconditional. Sibling of [[feedback_no_defensive_fallbacks]], which is about substituting a plausible value, and [[feedback_not_run_is_not_pass]], which is about a check reporting a pass it never earned; this one is about which branch an unrecognised value takes.
