---
name: feedback_subagent_calls_the_real_function
description: Restating logic that exists as code — in a subagent's prompt, or by reading a rule's prose to prescribe a fix — yields a confident wrong answer; import and call the real function instead
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

**The same reflex fires with no subagent in it.** A convention that ships as a runnable
checker is prose in its README and code in its rule file, and reading the prose to
prescribe a fix is that restatement one layer up. 2026-09-29: version 008's three
clauses were read from its README and a compose service rename prescribed that met two
of them — the name carried the repo's name but not its compose *project's*, which was
longer — and that rename reached the user as the fix before anything measured it.
Importing the rule module and calling it named the surviving deviation in one command.
So run the checker against the candidate fix, not only against the current state: the
prose says what the rule means and the module says what it answers, and a fix is a
claim about the second.
