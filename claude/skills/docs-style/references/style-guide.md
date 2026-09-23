# Worked pairs

Every pair below is real: the ❌ is text that shipped in `docs/convention-versions.md`, and the ✅ is what replaced it after review. Two rounds of annotation on one document produced 35 findings, and the document had been written carefully both times. That is the point of keeping the originals — they do not look like bad writing until the better version sits beside them.

## The opening

### Definition-first instead of reason-first

❌
> A convention in this repo is a claim about every repo on the machine. A rule in `claude/CLAUDE.md`, a pattern in `git/gitignore`, a directory layout a skill expects — change one and every other repo is left in the old shape, with nothing anywhere saying so. The first such change made by hand missed one repo entirely and left five more holding the work uncommitted.

✅
> Dozens of repos depend on this one: the rules in `claude/CLAUDE.md`, the patterns in `git/gitignore`, the skills and the directory layouts they expect. Ordinarily that dependency would mean never breaking any of it — a change those repos cannot absorb has no way to reach them, and no way to report that it did not.
>
> **Conventions are how a breaking change ships anyway.**

Three separate faults in the ❌, and they travel together:

- It defines rather than motivates. The reader learns what the word means before learning why anyone needed the thing.
- It narrates. The em-dash clause is built as a small reveal, and the third sentence is an anecdote staged as proof.
- It justifies. The document describes a system that exists; nothing in it has to argue that the problem was real.

The review comment was *don't write it as a novel with breathtaking plot twists; instead write why do we need this to begin with*.

### A category announced instead of shown

❌
> A convention change splits in two, and the halves are kept apart on purpose. What a repo has to do **once** … ships as a numbered **version**: … What has to hold **continuously** … ships as a **rule**.

✅
> **Conventions are how a breaking change ships anyway.** When a **convention** changes in a way that breaks backwards compatibility, a numbered **version** is published with it: a folder of prose saying what a repo still in the old shape has to do.
>
> A version says what a repo does **once**. A convention also carries **rules** — what has to hold **continuously** afterwards …

"A convention change splits in two" announces a taxonomy before the reader has any use for one. The ✅ lets the split fall out of the explanation, so the reader meets each half where it does work.

### A paragraph about the document

❌
> This page describes that system end to end — the version, the record, the checker and the two kinds of rule it runs, and what "current" does and does not mean. The agent-facing procedure lives elsewhere; the last section names the file for every piece.

✅ *(deleted)*

A table of contents written as prose. The headers already do this, the last section already names the files, and a reader who needs a map will scroll. Every document accumulates one of these; delete it on sight.

## Structure

### A header that names a metaphor

❌ `## The loop` ✅ `## How a repo catches up`

❌ `## Why a version is a migration and a rule is not` ✅ `## Why versions and rules stay separate`

The first pair trades an abstraction for the thing itself. The second untangles a negation — a header a reader has to parse twice is a header that failed.

### A list with no lead-in, whose first item was the lead-in

❌
> ## The loop
>
> 1. **A convention changes in this repo**, and the change ships with its version folder, committed alongside.
> 2. **Every other repo is now one version behind** — a fact derived from two integers, not stored anywhere.
> 3. **The session-start notice says so**, in that repo, on screen.
> 4. …

✅
> ## How a repo catches up
>
> A convention changes here, and the change ships with its version folder, committed alongside. Every other repo is now at least one version behind — a fact nothing stores, derived by comparing the number that repo recorded against the newest one here. Three steps close the gap, and none of them run unattended:
>
> 1. **The session-start notice says so** in that repo, the next time a session opens there.
> 2. …

Items 1 and 2 were never steps — they were the situation the steps respond to. Promoting them to a lead-in gave the list a frame and shortened it. The review comment was *that's not a straight-forward header; before going into the list, there should be text description of what we are talking about; probably most of it comes from item 1*.

### Two kinds buried in a paragraph

❌
> A second, smaller class of rule is gated by no version at all and runs in every repo the moment it is committed here; the checker's section below says what belongs there and what it costs.

✅
> Rules come in two types:
>
> - **Versioned rules** are introduced by a particular version, and run only where the adopted number is at or above it. A rule introduced by v11 does not run in a repo at v10.
> - **Universal rules** are gated by no version, and run in every repo from the moment they are committed here.

The ❌ mentions a second class without ever listing the first, and defers the substance to a later section. The list format forced both halves to be stated, and the concrete v11/v10 sentence exists only because the list left a slot for it.

## Sentences

### Passive voice hiding the actor

A numbered procedure describing what `/adopt` does, with `/adopt` absent from every line:

❌
> 1. **Its README is read in full**, before anything is touched.
> 2. **The "When it does not apply" conditions are checked against this repo** …
> 3. **Otherwise the migration is performed** as the README instructs, and every mutation is shown before it happens …

✅
> 1. **It reads the README in full** before touching anything.
> 2. **It checks the "When it does not apply" conditions against this repo** …
> 3. **Otherwise it performs the migration** as the README instructs, showing every mutation before it happens …

### Self-defending clauses

Each ❌ below was deleted whole. None of them carries information; each argues that the sentence before it was a good idea.

| Deleted | Attached to |
|---|---|
| *…and the halves are kept apart on purpose* | the version/rule split |
| *…rather than sampled whenever somebody remembers to go and look* | the checker running at every commit |
| *The continuing half has no loop.* | the rules section |
| *the checker's section below says what belongs there and what it costs* | universal rules |
| *That reach is why this is the smaller class **on purpose**.* | → *That reach is why this class stays small.* |
| *The difference is deliberate and it is written down.* | → *The difference is written down.* |

### Stating what was just read

❌
> A session-start notice prints the gap, `/adopt` walks it, `/commit` commits the result, and the checker keeps the rules holding from then on.

✅
> A session-start notice prints the gap, `/adopt` walks it, and the checker holds the rules from then on.

The annotation on *`/commit` commits the result* was two words: **who could have thought**.

### Cumbersome phrasing

❌ *Someone runs `/adopt` there, in that repo's own session.*
✅ *Someone runs `/adopt` in that repo.*

❌ *the number advances by exactly one* ✅ *the number advances by one*

❌ *A repo's state is one integer* ✅ *A repo's record is one number*

Three separate notes produced these: *cumbersome writing*, *unnecessary word*, and *that's too generic term* — the last on `state`, which named nothing the document could point at.

### Over-precision that reads as emphasis

❌ *a fact derived from two integers, not stored anywhere*
✅ *a fact nothing stores, derived by comparing the number that repo recorded against the newest one here*

The annotation was *you don't have to emphasize that it is an integer - just version number*. Naming the type where the reader needed the operands is the mechanism-instead-of-intent error at sentence scale.

### A reference that resolves differently per reader

❌
> The same shape cost this project a queue item that reported cost, seats and station addresses as "not provided".

✅
> The same shape cost the trips project a queue item that reported cost, seats and station addresses as "not provided".

Found in review rather than from an annotation. The sentence sits in a global memory, which renders into every session's `CLAUDE.md`, so *this project* named whichever repo happened to be open — right in one of them and wrong everywhere else.

## Scope claims

❌ *A convention in this repo is a claim about every repo **on the machine**.*
✅ *Dozens of repos depend on this one.*

The annotation was a single character: **?**. The repos span two machines, so the claim was scoped to one of them by accident — invisible to every reader who does not already know the answer. Write the scope you actually checked.

## What the external skills add

Two public Claude Code skills cover this ground, and both are small and lightly maintained. Worth mining, not adopting:

- **[Xamfonos/technical-writing-best-practices](https://github.com/Xamfonos/technical-writing-best-practices)** (MIT) — 26 principles in 5 domains, each with a ❌/✅ pair. Its *Introduced Abstractions*, *Thesis Spine* and *Signal-to-Noise Density* are the same findings reached independently. Its *Reader Compression* — one idea per sentence, break at each new action — is a rule this file does not otherwise carry.
- **[gwagjiug/technical-writing](https://github.com/gwagjiug/technical-writing)** (NOASSERTION, bilingual KO/EN) — its `sentence-style.md` bans the meta-discourse openers (*In this document, we will explain…*, *It is important to note that…*, *As mentioned above…*), and adds two rules worth keeping: never polish inside a code block, and never cut a warning, prerequisite or edge case to make a page shorter.

Anthropic's own [`doc-coauthoring`](https://github.com/anthropics/skills/tree/main/skills/doc-coauthoring) is an authoring *workflow* — gather context, draft section by section, test with a fresh reader — with almost no prose rules. Its one transferable habit is the last stage: hand the finished draft to a reader who has not seen the work, which is what the annotation rounds behind this file actually were.
