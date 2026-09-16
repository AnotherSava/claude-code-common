---
name: feedback_subagent_calls_the_real_function
description: A subagent told to reproduce production logic in its prompt returns a confident wrong number with a credible method section; have it import and call the real function instead
metadata:
  type: feedback
---

**When a subagent must measure what production code computes, tell it to call that
code — never restate the rule in its prompt.** A prompt-level restatement is a second
implementation, and it silently drops whatever the real code also does.

**Why:** 2026-09-15. A survey agent was asked which `package.json` files the adopt
walk returns across the fleet, and the prompt spelled out the rule — walk the tree
skipping these 21 directory names. It did exactly that and reported 22 manifests in
the dotfiles repo, "19 tracked fixtures plus 3 ignored ones", with a `method` section
naming every command it ran. The real `manifests()` returns **one**: the restatement
had no `_own_fixtures.prune`, the identity check that refuses the skill's own fixture
tree. Wrong by a factor of 22, and it read as *more* rigorous than a correct answer
would have, because the methodology was spelled out and the methodology was the error.
A second agent, told to critique the survey, caught it; running `manifests(".")`
myself settled it in one command.

**How to apply:** the tell is a prompt containing a list, a threshold, or a filter
that also exists in the code. Replace it with an import and a call — "add that
directory to `sys.path`, import the module, print what the function returns" — so the
agent measures the thing rather than a description of it. Where calling it genuinely
is not possible (another machine, another language), treat the number as a claim and
check one case against the real function before building on it; see
[[feedback_no_guessed_facts]]. The failure is not a missing answer, it is a confident
wrong one with a credible method section attached. Related: [[feedback_check_the_limit_is_real]]
is the same reflex applied to a general rule whose premise you never checked.
