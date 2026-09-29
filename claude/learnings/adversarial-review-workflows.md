# Authoring adversarial review workflows

Notes on the find-then-refute shape — parallel reviewers raise findings, independent agents try to kill them,
survivors get reported. It works: across four rounds on one change it caught a false user-facing string, a
behavioural regression, and two docs that confidently described code that did not exist. These are the ways it
quietly fails.

## Run it read-only, and keep fixing out of the round

Give every agent an absolute read-only constraint and let the workflow return a report. Not a
politeness — a mixed round does not converge. Across eight rounds on one feature, three of the
blocking defects were introduced by the *previous* round's fixes, because the tree kept moving
while reviewers reasoned about it. The first read-only round found five defects that seven mixed
rounds had missed.

State it as a constraint the agents cannot read past, and name the mutating commands explicitly
(`cargo fix`, `git checkout`, `git stash`, package installs) — "review this" is not enough.

Two things make the round land better:

- **Tell them what is already settled**, with the evidence. A reviewer that re-derives a
  measurement you have already taken spends its budget on nothing, and one told "this path was
  observed working end to end" will hunt where evidence is actually thin.
- **Tell them the author's fixes have broken things before**, when true, and to treat each change
  as guilty until proven innocent. Round four of that feature was scoped as an audit *of the
  fixes* rather than a fresh sweep, and it was the first to return no blocking findings.

## Give each agent its own scratch directory, and name the repo in every git command

Read-only does not hold once agents run experiments. Give every agent a scratch path of its own,
built from its label or index rather than shared by a dimension; forbid `rm -rf` outside it; and
require `git -C <absolute path>` instead of `cd`. Each Bash call starts in the reviewed repo, so a
`cd` that fails leaves every command after it running there.

Measured 2026-09-28: the verifiers of one dimension shared a scratch root, and one deleted it while
a sibling was mid-test. The sibling's next `cd` failed, and its scratch commands ran in the reviewed
repo instead. It set a local `core.hooksPath` that switched off the signature and attribution gate,
`commit.gpgsign=false` and a throwaway identity. Then it made an unsigned commit sweeping up every
pending change. Its `git push origin master` failed only because the branch was `main`.

After any workflow whose agents ran git, check the reviewed repo before trusting it:
`git status -sb`, `git reflog -3`, and `git config --local --get-regexp '^(core\.hookspath|user\.|commit\.gpgsign)'`.
Ask for those keys by name, since a transcrypt repo's full config listing includes its passphrase.

## Never gate the verify stage on the finder's own severity rating

The bug that cost the most:

```js
const real = (res?.hits ?? []).filter((h) => h.severity === 'real')   // WRONG
if (real.length === 0) return []
```

Four finders returned eleven findings, every one self-rated `nit`, so nothing reached the judge and the
workflow's summary line read **"0 real hits, 0 stood"**. Taken at face value that is an all-clear. Several of
those "nits" were real defects — dead code the change had just created, a factually wrong comment, a
tautological SQL clause.

Finders systematically under-rate their own work: they have no idea what the other finders found, no sense of
the change's blast radius, and a prompt telling them not to report trivia. Severity is a **judging** decision,
so let the judge make it. Either send everything to the verify stage, or filter afterwards — and if you must
drop some, `log()` how many, because a summary that silently omits its inputs reads exactly like a clean run.

The general rule: **a filter placed before the stage that decides relevance will hide the thing that stage
existed to find.**

## Report the count you filtered, always

`log(\`${all.length} raised, ${confirmed.length} survived refutation\`)` is worth more than the findings list.
"5 raised, 0 survived" is a meaningful all-clear; "0 raised" usually means the harness is broken.

## Give refuters a real bar, in both directions

A refuter told only "try to refute this" refutes everything — it is the path of least resistance, and the
output looks rigorous. Spell out what counts as refutation, and that nothing else does:

- the code genuinely does not do what the claim says
- the state is unreachable through ordinary use
- pre-existing and untouched by this change
- a style or prose preference rather than a defect
- contradicts something the user explicitly asked for

and then add the counterweight explicitly — *"be honest in both directions; do not dismiss a real defect for
tidiness, and do not pass a nit to look thorough."* Without that sentence the refuters converge on dismissal.

## Count the votes as a majority, and never require unanimity to survive

The gate's polarity is easier to get backwards than it looks, and getting it backwards returns a
clean bill from a round that found plenty. Measured 2026-09-18: two refuters per finding, each told
*"default to refuted=true if uncertain"*, with survival written as

```js
const survives = votes.every(v => !v.refuted)     // WRONG — one uncertain vote kills
```

Thirty-one findings went in and `confirmed: []` came out. Every one of them was real, and the
biggest was a documented join that matched nothing in any of the four repositories it was written
for. The instruction and the tally compounded: told to default to dismissal, a skeptic unsure about
a finding it had not reproduced says refuted, and unanimity then lets that single vote decide.

Three refuters and a majority kill (`kills * 2 >= live.length`) is the shape that works, with the
"default to refuted" instruction removed — ask instead for a concrete reason the claim fails, and
say that not reproducing it is not one. The same round re-run that way confirmed thirty-five.

Report the ballot on each survivor (`survived 3/3`) rather than just the count. A finding that
survived 2/3 is a different object from one nobody could refute, and the distinction is free.

## A defect count that stops falling means the design is wrong, not the code

Successive rounds on the same artifact should converge. When they do not, the thing being reviewed
is the wrong shape, and further rounds measure that rather than fixing it.

Measured across four rounds on one convention migration: 31 confirmed, then 35, then 53, then 46 —
roughly 165 defects, in three successive designs of the same script. Each round's fixes were real
and each new design was blind to something the previous one had caught: joining records on a
timestamp mistook an unrelated entry from the same minute for a lost one's file, and counting
categories instead reported two records swapped across two buckets as correct, because the counts
cancel. The curve was the finding, not any individual item on it.

So decide the stopping rule before round three, and say it out loud: *if the next round does not
reduce the count, the artifact changes shape rather than getting another pass.* What replaced the
script there was prose telling an agent to read the two lists side by side — the matching was a
judgement about whether two texts describe the same thing, which is why no rule over strings ever
settled it, and why each fix traded one blind spot for another.

## A falling count can still be the wrong work: have them rate realism

A count that falls overall is no proof the rounds are worth running. A finder constructs every
scenario it can, a verifier confirms that the code mishandles it, and neither is asked whether anyone
will ever be in it. Measured across eight fix-and-review rounds on one app: the lists left open ran
seven, nine, eleven, five, six, five, two, then none, so the stopping rule above would have fired at
rounds two, three and five. The fixes added about 2,500 lines of source and tests, and a later audit
against the owner's standard — *rare, and harmless or cheap to handle by hand* — removed about a
thousand of them again: a watcher retarget for a sub-second window, millisecond timestamps no
emulator writes, junction detection for a warning line, calendar ranges for dates before 1900.

So put the standard in the finder's prompt and give the verifier a realism lens as well as a
correctness one: *who hits this — a known writer, a user report, a documented path — and what does
it cost unhandled?* A confirmed defect with no one in it is a note, a log line or a sentence in the
docs, not code. The audit that did the removal was the same shape as a review: area sweepers
listing every scenario-specific branch with a realism rating, one skeptic arguing to keep each
removal candidate, and a ranking. Its "keep" list, what prevented data loss, crashes, lost or
duplicated output, or a leak of the user's own identity, is the part the fix rounds should have
been limited to.

## Fix agents between rounds: no builds, then one integrator

Parallel fix agents on disjoint file groups in one working tree must not build: they share its build
output directory, and concurrent builds into it collide (measured on a .NET app, where that was
`bin/` and `obj/`). Give them no build step at all, then run a single integrator agent that builds
with the real gate's flags, runs the tests, and repairs dangling references and tests that pinned
removed behaviour — with an explicit rule never to restore removed logic unless a test proves a kept
behaviour broke. Reviewers after it stay read-only, and parallel reviewers do not build or run the
tests in the shared tree either, for the same reason: running the tests builds first. Hand them the
integrator's build and test result instead. A reviewer that needs to execute something does it in
its own scratch copy, as *Run the reference implementation against every real instance, not against
a fixture* describes.

Large per-group input — audit entries, file lists, notes — belongs in a gitignored JSON file that
each agent reads by key, not in the Workflow `args`. Pasting tens of kilobytes into `args` is where a
placeholder gets launched by mistake: one run went out with `"SEE_FILE"` standing in for every
group's items and had to be stopped before its agents edited anything.

## Feed them what is already verified

List, in the shared prompt, everything already established: the build passes, the emitted SQL is *this*, this
edge case is known and accepted, that dependency is deliberately absent. Otherwise a quarter of the findings
are re-discoveries of things you checked an hour ago, and each one still costs a judge agent to dismiss.

## Diversity of lens beats more reviewers

Reviewers given distinct lenses — intent-versus-request, data-model semantics, user-visible copy,
documentation accuracy, cross-feature regressions — find disjoint sets. The copy lens caught a false empty-state
string that three code-focused reviewers read past without noticing. Adding a sixth reviewer with no new lens
mostly reproduces the first five.

## Watch for the same defect arriving from several lenses

Three lenses independently reporting one line is not three defects; it is one defect and a strong signal. Dedupe
by file and line before the verify stage, or pay for the same judgement three times.

## In a triage workflow, refute the dismissals, not the findings

Everything above assumes a review, where the expensive error is a false positive and the refuter defends against
a finding that is not real. **Triage inverts it.** When the question is "is this backlog item still a problem?",
the expensive error is the false *negative* — closing something that silently reopens whatever it guarded — so
the refuter must be pointed at the `already-done` and `obsolete` verdicts and told the burden of proof sits on
the claim that the problem is gone. Default to `refuted=true` when it cannot be independently confirmed.

Measured on a 7-item triage: 5 first-pass verdicts came back as handled or partly handled, and **all 5 were
overturned.** A single-pass triage would have closed five live items.

Two failure modes drove nearly all of it, and both are worth naming in the refuter's prompt:

- **A working-tree edit read as a delivered fix.** Three verdicts rested on changes that existed only as
  unstaged bytes on the machine the agent was running on. Tell refuters to check the committed side
  (`git show HEAD:<path>`, `git log @{upstream}..HEAD`), not just the file.
- **"The reason is stale" read as "the problem is gone".** An item's rationale can be entirely obsolete while
  its ask is untouched. Make the refuter separate premise from conclusion explicitly.

Give the investigator a verdict vocabulary that has somewhere to put this — `still-open` / `partly-overtaken` /
`obsolete` / `already-done` — or a half-stale item gets rounded to whichever end is closer.

## Dedupe *after* the verify stage, not before — the duplicates are ballots

The section above says to dedupe by file and line before verifying, so one defect is not judged three times.
That is right about cost and wrong about safety, and the safety side is worth the money.

Measured on a 5-dimension review with 3 refuters per finding and a kill-on-majority-refute rule: one real
layout defect was reported by three dimensions in three phrasings. Two survived (refuted 1/3 and 0/3); the
third was killed **3/3**. Same defect, same file, opposite verdicts — the phrasing of the claim, not its
truth, decided which way the panel went. Deduping before the verify stage collapses those three ballots to
one, and if the survivor is the wrong one a confirmed defect is reported as clean.

So: let the duplicates run, and dedupe on the way out, keeping the *most* favourable verdict for each
`(file, defect)` rather than the first. The extra cost is a few judge agents; the failure it prevents is a
review that says nothing is wrong.

Two corollaries:

- **A split verdict is itself a signal.** One dimension refuting what another confirms means the claim is
  phrase-sensitive — usually a real defect described badly, or a scope disagreement (is it pre-existing?)
  rather than a factual one. Surface those rather than letting the majority silently settle it.
- **Verify the survivors yourself before acting.** The panel is a filter, not an oracle. The defect above
  reproduced in about fifteen lines of Playwright — 223px overlay against a 231px reserved margin, then 131px
  against the same stale 231px. Reproducing it took far less time than the review that found it, and is the
  only thing that turns "three agents think so" into knowing.

## Run the reference implementation against every real instance, not against a fixture

A review panel reading a design finds different defects from one executing it, and the gap is not
about care. Measured 2026-09-15 on a design for a convention-adoption system: four independent
designers, then three judges scoring them on fidelity, robustness and lifetime cost, all missed that
the winning design's central contract was inverted. Two critics told to *run* its reference script
against the real repositories found it within minutes, independently, and agreed.

The defect is worth stating because its shape recurs. A check was specified to verify that a
migration had *happened*, and the evidence it read was the pre-migration file — which the migration
deletes and the commit then removes from `HEAD`. So the four repositories that had done the work
*and committed it* were the ones it could not verify, and they would have been recorded "does not
apply". Every repository where the work was done worst still had its evidence lying around and
passed.

The generalisation: **a check whose evidence is destroyed by the act it verifies cannot tell done
from never-done**, and it fails precisely on the cases that went best. Reading the design cannot
surface that, because on paper the check is about the right subject. Only running it against
instances in several different states shows that the states are indistinguishable.

So budget a stage that executes, and point it at the real population rather than at fixtures the
same author wrote. Fixtures encode the shapes the author already thought of; a fleet of fifteen
repositories contains the ones they did not. Give that stage the standing permission to copy real
data into scratch and mutate the copy, and the standing prohibition on touching the originals.
