---
name: docs-style
description: >-
  How a document is written — what it opens with, how it is structured, and which sentences do not belong.
  TRIGGER when: writing, revising, restructuring or reviewing any long-form prose this repo or a project keeps — a docs/ page, a README section, a learnings file, a convention version README, a memory file body, or a comment running past a few lines. Invoke BEFORE the first draft, not after.
  DO NOT TRIGGER when: the question is whether a document is still true or complete (that is `docs-relevance`), the text is a commit message (`shared/commit-message-rules.md`), or the subject is how Claude's chat replies are shaped (that is the output style, tuned through `tune-output`).
allowed-tools: Read, Edit, Write, Grep, Glob
---

# Writing a document

Every rule here was paid for by a review round on a document that already read well to its author. That is the thing to expect: prose that feels informative while being written is exactly what a reader finds bloated, and no rule below is detectable by re-reading your own draft sympathetically.

Read `~/.claude/skills/docs-style/references/style-guide.md` for the worked before/after pairs. This file is the decision procedure; that one is the depth.

## When the path already answers it

Ask nothing where the file's location fixes the reader. These conventions do not move, so a question about them spends an exchange to be told what the path already said.

| Path | Reader | This file |
|---|---|---|
| A skill's own files — `SKILL.md`, and whatever it ships under `references/` or `scripts/` | Claude, executing the procedure | Does not apply |
| `learnings/<topic>.md`, `memory/*.md` | Claude, consulting it mid-task | Applies |
| `README.md`, `docs/**`, a convention version README | A person | Applies — ask the questions below |

**A skill's own files are out of scope, not merely a different depth.** Every rule here is about how a document reads to a person: an opening that gives the reason before the definition, a header whose content a reader can predict, a sentence that does not defend itself. A SKILL.md is a procedure Claude executes, and its constraints, commands and edge cases *are* the content — trimming them so they read better removes what a run needs. Leave them alone.

**Name a learnings file for the problem shape when its rules outlive the tool.** That directory is indexed by filename, so `postgres-copy-prod-to-dev.md` is invisible to someone doing the same job on another engine — and four of its five traps were never about Postgres. Tool-named is right where the content is genuinely about that tool; shape-named is right where one tool is the worked example under rules that are not.

Ask the questions below only where the path does not decide.

## Before the first sentence, ask

**Who the reader is and what they want the document for are the user's to tell you, not yours to infer.** Ask before drafting or rewriting, and do not start until the answers are specific. Every rule further down this file operates *within* those answers — get them wrong and a document can satisfy all of them and still be the wrong document.

**Neither answer is a property of the file.** The same document serves a reader challenging the design, a reader operating the thing, and a reader extending it, and those three want different depths of the same material. A section that is noise this week is the whole point next week. So the questions get asked per piece of work, not once per document and never inherited from whoever wrote it last.

Ask these, and ask them as questions rather than presenting a draft and waiting to be corrected:

1. **Who opens this, and what has just happened to them?** A reader arrives mid-problem, not at the start of a story.
2. **What are they trying to do with it?** The three common answers pull in different directions, and the topic does not decide between them:
   - *Judge the design* — wants the concepts and the reasoning, and treats mechanism as a distraction. Commands, schemas and internal interactions are noise here however correct they are.
   - *Operate it* — wants the commands, the failure modes and what to do about each.
   - *Extend or maintain it* — wants the schemas, the contracts and the internals the other two want cut.
3. **What do they already know?** This sets how much is assumed rather than explained, and it is the question most often skipped.
4. **What is the one claim the document is making?** Everything that does not serve it is a candidate for deletion, however true.

**On a rewrite, the existing document is not evidence of the right level.** It encodes whoever wrote it last and what they assumed, and a revision pass that only fixes sentences silently ratifies all of it. Ask the same four questions before a rewrite as before a first draft — and where the answer has changed, say so out loud, because entire sections are then in scope rather than individual paragraphs.

Measured: one document took three review rounds. The first two produced 35 findings, every one of them at sentence level, and both were applied faithfully. The third round said the *depth* was wrong — a reader who wanted to challenge the concepts had been given the agent-to-agent interactions and the scripts — and cut 130 lines, including whole sections the first two rounds had carefully polished. The question that would have prevented it costs one exchange and was never asked.

## The opening

**Lead with why the thing exists, not with what it is.** The first paragraph earns the rest; a definition does not.

A definition-first opening is the most common failure and the hardest to see, because it is correct. Its tell is that the first paragraph would survive unchanged in a glossary.

❌ *A convention in this repo is a claim about every repo on the machine. A rule in `CLAUDE.md`, a pattern in `gitignore` — change one and every other repo is left in the old shape.*
✅ *Dozens of repos depend on this one. Ordinarily that dependency would mean never breaking any of it — a change those repos cannot absorb has no way to reach them, and no way to report that it did not.*

The first says what a convention is. The second says why anyone built the system, which is the question a reader actually arrives with.

**Do not narrate.** A document is not a story with a reveal. Statements set up to land as turns — *and then the real problem appeared*, *but there was a catch* — spend the reader's attention on pacing rather than on content. State the situation, then the response.

**The opening needs no justification.** A document describing a system that already exists is not a proposal, and nothing in it has to argue for its own existence. Cut the anecdote that proves the problem was real; the reader is here because they already have it.

## Structure

**A header says what its section is.** A reader scanning the table of contents should be able to predict the content. Metaphors, clever labels and abstractions read as filler at the exact moment someone is trying to navigate.

❌ `## The loop` · `## Why a version is a migration and a rule is not`
✅ `## How a repo catches up` · `## Why versions and rules stay separate`

**A list needs a prose lead-in that says what is being listed.** Dropping straight from a header into numbered steps makes the reader infer the frame from the first item. Where an existing first item is really the setup, promote it to the lead-in — a four-step list often turns out to be one sentence and three steps.

**The lead-in describes the set, not its members.** Saying what is being listed is its whole job. A lead-in that reaches in and characterises particular items — *the first three are settled before it starts*, *only the second announces itself* — hands the reader a claim about things they have not read yet, and they spend the list checking it instead of reading it. Whatever you wanted to say about an item belongs on that item.

Ordinal references into a list rot on top of that: *the second*, *the last*, *the other two* are all wrong the moment an item is added or the order changes, and nothing flags them. Same failure as anchoring a range on today's last item, one construct down. Two lead-ins in one document carried four such ordinals between them, and the list under one of them was reordered in the same review — which would have falsified its own lead-in with nothing reporting it.

**When something has two or three kinds, make them a list.** Two types described in a flowing paragraph read as one blurred thing. The list is what makes the distinction visible — and it forces you to say what distinguishes them, which prose lets you skip.

**Introduce a term the first time it carries weight, and mark it.** Bold the term at the point of definition so a reader landing mid-document can find where it was explained. Do this for the handful of terms the document itself defines, never for emphasis.

**Answer the question you just raised.** Naming a component raises the obvious follow-ups — where does it come from, who updates it, what gates it, does it apply to me — and a document that introduces the thing and moves on leaves the reader holding them. This is the one fault a writer cannot feel: you know the answers, so the gap is invisible from the inside.

Two annotations on one document were exactly this, both on a single word:

> `checker` — *how the checker is updated, and where does it come from?*
>
> `rule` — *are rules (always?) related to particular version? are they applied only to repositories above that version?*

Neither asked for better wording; both asked for a fact the document never supplied. Answer it where the term is introduced, not in a later section — a reader who has to hold a question for four sections has already stopped trusting the text. After a draft, list the nouns you introduced and ask each one *where does this come from* and *does it apply to me*.

## Sentences

**Name the actor.** Passive voice hides who does a thing, and in a document about a system the actor is usually the answer the reader wants.

❌ *Its README is read in full, before anything is touched.*
✅ *It reads the README in full before touching anything.*

Passive is correct where the actor is genuinely unknown, irrelevant, or deliberately unnamed. It is wrong as a default register.

**Cut every sentence that defends the text around it.** These arrive as reassurance and read as insecurity. They are the single largest source of removable words.

The forms to search for:

- *…and the halves are kept apart on purpose*
- *…rather than sampled whenever somebody remembers to go and look*
- *This page describes that system end to end — the agent-facing procedure lives elsewhere*
- *The difference is deliberate and it is written down*
- *…which is exactly what X kept trying to be*

**Describe the current state, not the route to it.** A document says how the thing is. How it got that way is the author's memory leaking into the reader's document — it felt significant to write because you were there, and it is dead weight to someone who was not.

The tell is the past tense about something that no longer exists: *used to sit beside it*, *was renumbered once*, *it stopped being one*, *that half is gone*. Two whole sections of one document matched it — the history of a numbering change, and a retired second file — and both were cut in full. Git holds them: the commit that removed a thing carries its full text in the diff, so nothing is lost by leaving it out of the prose.

Keep history in exactly two cases, and say which one applies:

- **The reader may still be holding the old artifact** — an old export, a number written down before a renumbering, a config in the previous format. Then the history is a live instruction, not a story.
- **A constraint from back then still binds** — an odd name, a field nothing reads, a workaround something still depends on. Explain what binds now and mention the cause in a clause, rather than narrating the sequence.

Anything else — what was tried, what it replaced, when it changed — belongs in the commit message, a learning, or a changelog.

**A document read from many places cannot say "here".** *This project*, *this repo*, *the current config* resolve against wherever the reader happens to be, which is the one thing the writer does not control. A global memory renders into every session's `CLAUDE.md`, so its *this project* names whichever repo is open — right in one of them and wrong everywhere else. Name the thing: *the trips project*. Caught 2026-09-22 in a memory whose evidence sentence cited a defect from a different repo.

**Never state what the reader has just read.** A sentence whose content the previous sentence already implied insults the person following along. The review comment this earns is *who could have thought* — for a line saying `/commit` commits the result.

**Cutting has a floor, and you will find it by going through it.** Every rule above removes words, so the failure they produce together is a sentence so compressed that the reader cannot reconstruct what it means. That reads as confident and says nothing.

❌ *Rules are not adopted, they are run.*

Four words carrying a distinction the reader has no way to unpack — the review comment was *that's confusing — more details needed?*. The fix is not to restore the cut sentences but to say the thing: what gates each kind, and what that means for a given repo. **A cut that leaves the reader inferring is not a cut, it is a gap.** Test it by reading the sentence as someone who does not already know the answer.

**Pick the noun that names the thing.** A category word — *state*, *data*, *information*, *handling*, *process* — passes review because it is never wrong, and tells the reader nothing they could act on.

❌ *A repo's **state** is one integer* ✅ *A repo's **record** is one number*

The annotation was *that's too generic term*. When no precise noun exists, that usually means the concept has not been pinned down yet, and the sentence is hiding the gap rather than the word being hard to find.

**Say it the short way.** Where two phrasings carry the same information, the shorter one is correct, and the longer one was usually reaching for rhythm.

❌ *Someone runs `/adopt` there, in that repo's own session.*
✅ *Someone runs `/adopt` in that repo.*

**Cut a word that adds nothing.** `exactly`, `simply`, `actually`, `of course`, `it is important to note that`, `as mentioned above`. Keep a qualifier that carries real uncertainty; delete one that performs precision.

## Warnings

**Say what to do, then why.** A warning that opens on its reason makes the reader assemble the instruction themselves, and they are reading a warning because they are already in a hurry.

The two halves fail independently and each failure looks fine alone. A warning with no instruction states a fact and asks for nothing. A warning whose reason is something the reader could have supplied — *because this is important*, *to avoid problems* — justifies the instruction with nothing and gets skipped. Write the imperative, then a reason that forces it: why it has to happen now, or in that order. Full case in `~/.claude/memory/feedback_warning_leads_with_instruction.md`.

**A comparative frame says both options work.** *Recreate the one service rather than the stack* reads as a preference between two things that function, however forcing the reason after it is. Where the alternative actually fails, name the failure: *remove the old container first — the publish aborts on a name conflict otherwise*. Measured 2026-09-20: a reader met that exact line in a convention version, understood it, filed it as an optimisation, and hit the abort.

## Claims that decay

Three rules share one shape: the sentence is **correct the day it is written**, nothing touches it, and it becomes false. Review never catches them, because reviewing means re-reading a true sentence.

**Do not widen a claim past what you checked.** A sentence saying "every repo on the machine" when the repos span two machines is wrong in a way no reader can catch. Write the scope you verified.

**Do not narrow one either.** A bound stated tighter than the truth is the same fault mirrored, and it is easier to write because the tight version reads cleaner. *Every other repo is now one version behind* is false the moment two versions ship before anyone adopts — the annotation was one phrase, *at least*. Where a quantity is a floor, say so.

**Never quote a count of a set that changes.** "All three tenants", "the count must be 8", "the seven keys below" — each is wrong on a schedule. Cite the property or the command that yields the number instead: *every tenant that publishes reaches it*, *the count must agree with the manifest — read it with …*. A cutover runbook once carried a **stop** instruction keyed to the literal 8; a fourth tenant staged in the working tree would have halted the cutover for an entirely correct reason. Where an example number helps a reader recognise output, label it as an example and put the assertion on the comparison. Dated historical records are exempt — *verified on 2026-08-27, all three asserted* is a claim about a moment. Full case in `~/.claude/memory/feedback_cite_the_source_not_the_count.md`.

**Anchor a range on what cannot move**, which is the `CLAUDE.md` Prose Style rule — not restated here. Read it with `~/.claude/memory/feedback_drift_proof_doc_anchors.md`, which carries the part the summary drops: a terminal *name* used as a bound rots on the same trigger as a line number and is sneakier, because it carries no digits to flag it.

## Rules that live elsewhere

`CLAUDE.md`'s **Prose Style** section is injected into every session, so its three rules are already loaded whenever you write anything and this file does not repeat them: no sentence opening on a backticked code span, parallel enumerations sharing grammatical form, and the drift-proof anchor rule above. Treat them as in force here.

`CLAUDE.md`'s **Overused Phrases** section governs every authored text, documents included. It is a live blocklist — read it, do not summarise it.

## Before handing it over

Run these three passes separately. Together they collapse into one sympathetic re-read, which finds nothing.

1. **Read only the headers.** Does the sequence tell the story? A header you cannot predict the content of is a header to rewrite.
2. **Read only the first sentence of each section.** Each should say what the section is for. A section opening on a detail has buried its own point.
3. **Delete every sentence you can, one at a time, and ask what the document loses.** Most lose nothing. That is the finding, not a reason to stop early.

Then: is any paragraph arguing for a decision that is already made? Is any sentence explaining the mechanism where the reader needed the intent? Both are cuts.

## Out of scope

- Do NOT restructure a document's *content* to match a house shape — the layout of a docs site belongs to `github-pages`, and whether a page is still accurate belongs to `docs-relevance`
- Do NOT apply these to code comments shorter than a few lines, commit messages, or chat replies
- Do NOT apply these to a skill's own files — `SKILL.md` and what it ships beside it are a procedure for Claude, not prose for a person; see the path table above
- Do NOT rewrite a user's own words in a quote, an annotation, or a verbatim block
- Do NOT cut a warning, a prerequisite, an assumption or an edge case to make a page shorter — brevity is never a reason to drop a constraint the reader needs
