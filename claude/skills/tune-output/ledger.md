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

---

## 2026-09-10 — Second pass: the read-first block, and a body budget

**Source:** the user, twice in one session. First: "the actionable item in your last message is hidden in the
second sentence of the one-before-last paragraph, which takes a lot of effort to find". Then, after being handed
a seven-pair A/B sheet to judge: "I only check the actionable item and if there are any concerns raised... in
most cases I just read one line or one paragraph, I feel stupid reading two screens of text for each problem...
Maybe output should be two parts: the part that I should read first, and the part that I should read only if I
need more context."

**Mechanism:** the output style at `claude/output-styles/action-first.md`, rewritten rather than amended. The
phrase ban went to CLAUDE.md's **Overused Phrases** instead, per the usual split.

**Corrected mid-pass, twice, and both corrections matter more than anything below them.**

1. *Placement.* This pass first put the read-first block at the **top**, on my paraphrase that the user "reads
   the top and stops". They had said no such thing -- they read the *actionable part*, wherever it is -- and
   they made the argument that settles it: a terminal viewport sits at the END of a response, so the last
   paragraph costs nothing to find while the top of a long reply has scrolled away. The ask is therefore the
   **last** paragraph. My own earlier candidate had said exactly that and I had rejected it on the misquote.
   **Never paraphrase a stated reading habit into a stronger claim than was made** -- the whole design hung off
   one invented word.
2. *Container.* The block was a blockquote gutter. The user's objection was not the marker but the contents:
   of the two "concerns" in the reply that prompted this, one was a scratch PNG I was about to overwrite
   myself. A marker cannot fix admission. So: a single `→` on the action line, a `-` bullet for at most one
   concern, no gutter, and the blockquote is NOT reserved after all. The arrow then went too, on the user's
   call: with the position fixed at the end, a prefix repeats what the position already says, and it made the
   paragraph read as a form waiting to be filled. **The ask now has no marker at all** -- the last paragraph
   simply is the ask when there is one. Three rounds of typography ended at none of it; the rules that survived
   are the cap and the admission test.

**Adopted:**

- **The closing ask.** The LAST paragraph carries what needs the reader, and exists only when something does.
  An imperative sentence plus at most one sentence of concern, unmarked. **Most replies have no ask, and that
  base rate is stated in the file the model reads** -- it is the main defence against the invented-content regression recorded last pass,
  because there is no unconditional position waiting to be filled.
- **A hard cap of one action and one concern,** which is the rule that does the real work. The user's objection
  was never the formatting: "is it that important to tell the user about, to make sure the user reads it?"
  Without a cap the closing paragraph accumulates whatever seemed notable, the reader learns to skip it, and
  nothing is read at all. When two concerns compete the weaker is a detail by construction.
- **The admission test, and what it excludes.** A concern is about *their* world -- files, machine, data, the
  reliability of the answer, the premise of the request. Never the workbench: a scratch file, an intermediate
  artifact, a probe about to be overwritten, a temporary setting on its way back. **If you are going to fix it
  yourself, it is not theirs to carry.**
- **At most one bold run in the body.** The reply that triggered this already bolded its action; it was missed
  because three other spans were bold too. Weight does not survive competition with itself.
- **A body budget: 120 words,** lifted only by an explicit request to explain, an answer that *is* an
  enumeration, or a skill's mandated format. This is the half of the complaint the four candidate designs all
  missed and three of them admitted missing: every one relocated the action without shortening anything. The
  user was asked which complaint was operative and chose both.
- **Off-surface observations get one line, not a paragraph** -- `Noticed elsewhere: X. Memo it?`
- Explicit resolutions the old file left implicit: a live plan tool does not absorb an action the user must
  take; `AskUserQuestion` replaces the block rather than duplicating it; a skill's mandated output format
  replaces both parts.

**Rewritten:**

- *"name one concrete thing at the end"* -> open **with the user** goes in the block, never at the end and never
  in both places; a question parked by my own decision is a detail, not an open item. The untested guard clause
  against inventing a prior exchange is carried through **verbatim**, so the next A/B measures the same string.
- *"reading only the first line and the last line..."* -> read only the block; then delete each block line in
  turn and see whether its absence changes what they would **do** or only what they know.
- *"an observation ... moves to one labelled line at the end"* -> run it through the inclusion test first; the
  leftovers get the one-line memo offer above. **Never write the memo unasked** -- CLAUDE.md reserves that for a
  yes, which is why the user's chosen option ("send them to memos") could not be taken literally.

**Rejected:**

- **"A blocking request goes on the last line, standing alone."** My own candidate, tested to the point of a
  generated sheet and then **superseded before it was judged**. It is backwards under the reading behaviour the
  user described an hour later: someone who reads the top and stops will never reach a reserved last line. The
  sheet was built and never read; do not resurrect the rule from it.
- **Named slots** (a fixed vocabulary of labelled lines). A slot is the exact shape that pressures a model to
  fill it, and this ledger already records one measured case of that.
- **`---` or a `## Details` heading as the separator.** Three reasons: it draws a second boundary over one
  already drawn; in a scrolling terminal a horizontal rule reads as *end of message*; and in GFM a `---` on the
  line after text is a setext H2, so the design would hang on a blank line a later edit can silently remove.
- **A blockquote gutter around the ask, and reserving the blockquote for it.** Highlighting the whole paragraph
  is weight the fixed position does not need, and reserving the marker cost a normal use of it for nothing. A
  one-character prefix carries the same signal. An emoji was rejected before it was offered: it renders
  inconsistently in a terminal and reads as noise.
- **`<details>`.** Does not fold in a terminal -- it prints its own tags.

**What would re-open it:** the 120-word budget is a guess at a number, not a measurement; if replies start
losing things the user then has to ask for, raise it or broaden the exemptions rather than deleting content to
fit. The last-line rule re-opens only if the reading behaviour changes.

**Tested:** the block itself is **untested**, and deliberately so. A seven-pair Opus A/B was generated for the
superseded last-line rule (real prompts from the user's transcripts across seven genres, two constructed traps,
isolation verified clean) and the user declined to judge it -- "I feel stupid reading two screens of text for
each problem just to choose a better view", which is itself the finding this pass acts on. A blind sheet costs
the reader exactly what the rule exists to save them, so for this pass the person who hit the problem *is* the
measurement.

The judges did name one probe worth building if a future pass wants to test sorting rather than preference:
plant a known concern in the prompt material and check which part it lands in. That is a correctness check, not
a preference test, and it needs nobody's eyes but mine.

**Do not re-litigate:**

- Relocation is not summarisation. The body stays full-strength on the rare reply that wants depth; the budget
  is a default with three named exemptions, not a ceiling on truth.
- A design that shortens by dropping a defect is disqualified -- CLAUDE.md's reporting rule is not negotiable,
  and "make it shorter" must never become "leave it out".
- The ask's absence is the common case and carries meaning. A reply that ends in ordinary prose is not an
  unfinished reply.
- No marker on the ask -- not a gutter, not a prefix, not an emoji. Settled over three rounds; re-open only if
  the closing position stops being reliably last.
- **The go-ahead form is `Next step: I'll <x>.` then `Continue?` alone on the final line** (the user's wording).
  `Next step:` states what a yes buys, where the earlier "send anything and I'll..." made them infer it; the
  one-word question sits at the exact spot reading lands. Where the takeover guideline applies, the next-step
  line says so -- that is the moment CLAUDE.md requires the asking. Generalised once: when the thing needed is
  something only the user can do, the paragraph names that and the closing question matches. Shape fixed,
  words not.
- The problem was never which marker to use. Two rounds went into gutters, labels and arrows before the user
  pointed out the actual defect was what got admitted. Tune the admission test before the typography.

