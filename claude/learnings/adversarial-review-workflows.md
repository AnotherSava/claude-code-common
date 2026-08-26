# Authoring adversarial review workflows

Notes on the find-then-refute shape — parallel reviewers raise findings, independent agents try to kill them,
survivors get reported. It works: across four rounds on one change it caught a false user-facing string, a
behavioural regression, and two docs that confidently described code that did not exist. These are the ways it
quietly fails.

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
output looks rigorous. Spell out what does *not* count as refutation:

- the code genuinely does not do what the claim says
- the state is unreachable through ordinary use
- pre-existing and untouched by this change
- a style or prose preference rather than a defect
- contradicts something the user explicitly asked for

and then add the counterweight explicitly — *"be honest in both directions; do not dismiss a real defect for
tidiness, and do not pass a nit to look thorough."* Without that sentence the refuters converge on dismissal.

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
