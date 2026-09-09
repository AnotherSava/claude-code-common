# Output tuning ledger

One entry per tuning pass, appended at the bottom, newest last. Read the whole file before proposing a
change — it is kept short so that is cheap.

Every entry carries these fields. **Rejected** and **What would re-open it** are the two that pay for the
file: a rejection nobody wrote down gets re-proposed within months, and one written without its re-opening
condition reads as permanent when it is not.

```markdown
## YYYY-MM-DD — <short title>

**Source:** where the idea came from.
**Mechanism:** which home it went to, and why that one.
**Adopted:** rules now in force.
**Rewritten:** rules taken only in an altered form, with what changed.
**Rejected:** rules not taken, each with its reason.
**What would re-open it:** the evidence that would justify revisiting a rejection.
**Tested:** how, and what the result was. "Not tested" is a legitimate value; a blank is not.
**Do not re-litigate:** conclusions settled here, so the next pass starts after them.
```

---

## 2026-09-08 — First pass: adopting an action-first response shape

**Source:** the third-party `i-have-adhd` skill/plugin (`github.com/ayghri/i-have-adhd`), evaluated on request
without installing it. Its core is a 140-line ruleset plus a SessionStart hook and a real eval harness.

**Mechanism:** a custom **output style** at `claude/output-styles/action-first.md`, selected by the
`outputStyle` key in `claude/settings.json`, with `~/.claude/output-styles` added to both README install
blocks. The forbidden openers and closers went into CLAUDE.md's **Overused Phrases** section instead. Chosen
over CLAUDE.md because a shape rule that always applies should not arrive through the channel the harness
hedges as "may or may not be relevant". Chosen over the upstream SessionStart hook because that route costs a
script per platform and delivers a message that ages backward. Full comparison in `references/mechanisms.md`.

**Adopted:**

- Lead with the outcome or the action; prose after it.
- Numbered steps for multi-step work, one bounded action per step, no step containing "and then" twice, fold
  trivial steps into the one before.
- The first-line/last-line read-back test before sending. This had no counterpart anywhere in the repo and
  fights nothing.
- Ban the alarm register in failure reports — "Uh oh", "Oh no", "There seems to be a problem".
- An explicit request to explain or walk through overrides the length rules; add headers so it can be skimmed
  back. Openers and closers stay banned.
- Precedence: the harness, an explicit instruction, and a skill's own numbered procedure all outrank the shape
  rules. This is the clause that makes the rest safe to apply globally.
- Let a plan or todo tool carry state rather than narrating the plan as prose.
- Delete an announcing first sentence, a recapping last sentence, an empty hedging adverb, and an idiom
  standing in for the literal action — while keeping every hedge that carries real uncertainty.
- Delete a first sentence framing your own action as a catch or a save — "Good thing I checked", "Glad I
  looked". **Added 2026-09-09, after the A/B ran, and therefore UNTESTED.** Origin: the user caught the
  phrasing in a reply written during this very pass. It is a string-level deletion, which is the safest kind
  to ship untested, but do not let it inherit the tested verdict below. Neither the existing sycophancy rule
  (which governs flattery aimed at the user) nor the announcing-first-sentence check (which governs what you
  are about to do) reaches self-congratulation about what you just did — the gap is why it needed its own
  item. The A/B could not have caught it: none of the eight prompts creates an occasion for it.

**Rewritten:**

- *Cap lists at five items* → **split past five, never drop.** The rule's own body prescribes splitting, but
  its heading says cap, and a heading obeyed literally would truncate exactly the enumerations
  `feedback_follow_skill_instructions` was written about.
- *Make completed work visible* → kept the format, welded on the verification requirement. As written it
  prescribes the shape of a success claim while requiring nothing about whether it was observed.
- *End with one concrete next action* → **only when something is genuinely open.** As written it manufactures
  a next action after work that is finished, which is the filler the repo already bans.
- The upstream forbidden-opener and forbidden-closer lists go into the existing **Overused Phrases** section of
  CLAUDE.md rather than into the style file. That section already has the better format — an entry with its
  replacement — and a second competing list would drift from it.

**Rejected:**

- **Specific wall-clock time estimates.** The only rule in the source that obliges an unverifiable number on
  every use, and the only one its own eval harness never tests. When Claude executes the steps, minutes are
  not measurable.
- **The "state cause and fix" template for errors.** The source's own results trace their single consistent
  regression to it: it pressures the model to name a cause the evidence does not support.
- **"Delete any 'by the way' sidebar"** from the pre-send list. Directly contradicts CLAUDE.md's requirement
  that every noticed defect be reported. The compatible form is the source's own routing rule — move it to one
  labelled trailing line.
- **The rationale framing and the skill's name.** Its opening asserts a characteristic of the reader. Rules
  here are named and justified by the behaviour they produce, so no personal characterization enters this
  public repo's history.

**What would re-open it:** time estimates become adoptable if expressed in a unit the model can actually count
— files to touch, call sites, steps — rather than wall-clock. The cause-and-fix template becomes adoptable if
phrased to permit "cause not yet identified" as a first-class answer. The sidebar deletion does not re-open;
it loses to a rule that is not negotiable.

**Tested:** eight prompts drawn from real transcripts, two arms each, blind side-by-side. Both arms loaded the
real global CLAUDE.md, so the comparison measured what the candidate adds rather than beating a bare Claude.
Two trap cases were included: an under-determined failure, and a completion report where two items only looked
verified.

The first run was **void** and was discarded. It used `--tools ""`, which is silently ignored, so both arms
had every MCP server live: one arm answered the VPS prompt by searching the user's Gmail and quoting real
provisioning emails. That is a comparison of who did research, not of prose shape. The isolation that actually
works is recorded in `references/ab-harness.md`; the run was repeated with it. Read that section before
trusting any future run's flags.

**Result: ADOPTED.** Candidate 3, baseline 1, two ties, two pairs unjudged.

- *progress-report* and *direct-answer* — user's blind calls, both for the candidate. The second is the one
  that mattered: it is the case where a shape rule could pad a one-line answer into structure, and it did not.
- *enumeration* — candidate, decisively: 18 must-have items against the baseline's 13, in 40% fewer words,
  split into must-have versus applies-sometimes. It ranked and compressed rather than truncating, which is
  the behaviour the "split past five, never drop" rewrite was for.
- *error-report* and *explain* — ties. Neither arm invented a cause on the under-determined failure; both
  ranked and gave a discriminating test. Depth survived the explicit request to explain, 585 words against
  588, both with skim-back headers.
- *completion-report* — **baseline won, and this is the finding to carry forward.** Both arms correctly
  refused to call the work done and caught both planted items. But the candidate fabricated a prior exchange
  ("you never came back on whether the import should be idempotent — I flagged it but we moved on"), where
  the baseline explicitly refused to invent ("I can't answer that from here without inventing a list"). The
  prompt was a single turn; no such exchange existed. Same failure family as the three rejected rules: a rule
  that rewards surfacing what is open creates pressure to produce something when there is nothing. n=1, so it
  could be model variance, but it is exactly what the trap was built to catch.

Two adopted items are outside this verdict because they were written after the run, and both are marked where
they are listed: the self-congratulation deletion, and the guard clause added in response to the fabrication
above ("never invent an open question, a loose end, or a prior exchange in order to have something to put
there"). The guard is the fix for the single measured regression and is itself untested — the obvious first
candidate for the next pass to re-run.

A rule added mid-pass is not a defect in the method, but it does mean the tested text and the shipped text
have diverged. Either re-run the arms before shipping, or record the divergence item by item as above. Never
let the second option go unrecorded, because a ledger that says "tested" over text that was edited afterwards
is worse than one that says nothing.

**Do not re-litigate:**

- The upstream plugin is not to be installed. Everything wanted from it is reachable with one file and one
  settings key.
- A custom output style must set `keep-coding-instructions: true`. Without it the built-in engineering
  instructions are silently dropped.
- An unknown `outputStyle` name is a silent no-op. A style that fails to install produces a normal-looking
  session that applies nothing, so verify the selection resolves rather than assuming it.
- Output styles do not reach Task subagents. A rule that must reach one belongs in CLAUDE.md.
