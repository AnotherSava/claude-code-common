---
name: feedback_no_guessed_facts
description: don't state a guessed URL/path/endpoint/flag or capability claim as known, widen a supplied fact past what was measured, trust an index line over the file it points at, or report one environment's measurement as a property of the tool
metadata:
  type: feedback
---

Don't fabricate a plausible-looking identifier — a URL, file path, API endpoint, config flag, filename — and present it as if known. Either verify it (grep the repo, read the docs, navigate to a page you can confirm) or state explicitly that you're inferring and ask.

**Why:** presenting a guess as fact burns the user's trust and time. A made-up `treatstock.com/3d-printing` quote-page path got denied, and the user had to challenge "is it in your guideline?" — the guess had no basis anywhere.

**How to apply:** before emitting a specific identifier, ask "do I actually have this recorded, or am I inferring it?" If inferring, flag it or confirm first. For a site path specifically, navigate to the site root and read the page to find the real route rather than guessing a subpath.

The same applies to **capability claims** — "X can't decode Y", "the API doesn't support Z", "that's a hard limit". These are usually one probe away from being settled, and asserting one wrongly doesn't just mislead: the recommendation built on top of it inherits the error. Prefer running the check to reasoning about it — `MediaSource.isTypeSupported`, a config read, a one-line request. Where no check is available, say which part is measured and which is inferred.

**Why (capability half):** "Chrome can't decode a 4K Dolby Vision stream at all" was asserted without testing, and the advice that followed ("leave the bitrate ceiling where it is") rested on it. The user pushed back with "can't it?"; one `isTypeSupported` call showed it decodes the profile-8 base layer fine, and the recommendation reversed.

A third vector: **paraphrasing a supplied fact wider than it was supplied.** A guess does not have to start from nothing — compressing an enumeration into a category silently asserts the claim about members that were never checked. Keep a received claim exactly as wide as it was given, or re-measure before widening it.

**Why (paraphrase half):** a peer reported, with line numbers, that four named repos' commit gates open with `set -euo pipefail`. That became "the neighbouring repos on this box" in a committed comment, which swept in a fifth repo whose gate has no `-e` and made the sentence false. Nothing was invented at any point; the error entered through the summary.

A fourth vector: **an index or summary line that disagrees with the file it points at.** The paraphrase half widens a claim; this one contradicts its own source, and it survives longer because both look authoritative. **An index entry is a pointer, not a source** — before quoting a number that carries an argument, open the file it points at, and when the two disagree the file wins and the index is the bug.

**Why (index half):** a project `MEMORY.md` line said `data/projects.7z` holds "~410 sessions retention has since deleted"; the file it linked said 48 (of 83 in the archive). The index was a file count wearing a session label. I quoted it into two cross-machine briefs — where the number *was* the argument for which machine to protect first — and a peer had to measure it to push back. Nothing outside the memory system was consulted, and nothing needed to be.

Finally, **scope a measurement to the environment that produced it.** Reporting "the tool emits nothing non-interactively" from three probes that all ran through one shell asserted a property of the *tool* from evidence about the *tool plus that shell*; a peer ran the same binary non-interactively through a different shell, where it worked. The prescription built on it survived, the stated fact did not. Name the environment an observation came from — especially when the recommendation would be identical either way, since that is exactly when the over-claim goes unchallenged.
