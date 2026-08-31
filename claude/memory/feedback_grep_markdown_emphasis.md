---
name: Grep for stale prose must survive markdown emphasis
description: When sweeping docs for outdated claims, emphasis markers split words — `grep "Node 22"` returns 0 against `Node **22 LTS**`
metadata:
  type: feedback
---

When sweeping documentation for a stale claim, a literal phrase search silently misses every instance where markdown emphasis interrupts it. `**bold**`, `*italic*`, `` `code` `` and line wrapping all split a phrase mid-search.

**Why:** the false negative is invisible and arrives with false confidence — you report the sweep clean. Real case (2026-08-24): after moving a project from Node 22 to 24, `grep -rn "Node 22"` over the repo returned zero remaining hits, so the sweep was declared complete. A memory file still carried `Base image: ubuntu:24.04 + Node **22 LTS** … **Not Node 24**` — a *standing instruction* to do the opposite of what had just shipped. The literal string was `Node **22 LTS**`, so `"Node 22"` could never match it. A sibling agent found it with a looser pattern.

**A separator-tolerant regex fixes emphasis and CANNOT fix wrapping.** grep is line-oriented, so no pattern — however loose its character class — matches across a newline. Second real case (2026-08-30): checking whether a sibling had adopted a correction, `grep -i "prefix assignment"` returned nothing while the file plainly said it, as `PREFIX` ending one comment line and `# ASSIGNMENT` opening the next. It was reported as not adopted when it had been. For a phrase that may wrap, either normalise first (`tr '\n' ' ' < file | grep -o "PREFIX # ASSIGNMENT"`, keeping the comment marker the wrap inserts), use a multiline matcher (`pcregrep -M`, `rg -U`), or — simplest and most robust — grep one distinctive **single token** and read the surrounding lines yourself.

**How to apply:** sweep with a pattern tolerant of separators between the words — e.g. `grep -rniE "node[ _*\`-]*\*{0,2}22"` — and search for the *concepts* as well as the phrase (here: `stricter env teardown`, `Not Node 24`, `build-from-source`, `>=22 <23`), since the wrong claim is often phrased several ways. Then confirm the survivors are deliberate history and framed as such ("HISTORICAL — do not follow", "withdrawn 2026-08-24") rather than live instructions. Related: [[feedback_live_values_source_of_truth]].
