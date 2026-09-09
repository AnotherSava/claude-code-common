---
name: tune-output
description: >-
  Change how Claude's replies are shaped — adopt, revise or reject a response-style rule — then record the pass
  in a ledger so the next one starts from evidence instead of from scratch. Owns the output style file, the
  blind A/B harness that tests a candidate before it ships, and the history of what has already been tried.
  TRIGGER when: the user wants replies formatted or worded differently, brings a response-style idea from
  another project or repo to evaluate, asks why a style rule exists or is missing, or says an existing style
  rule is not working.
  DO NOT TRIGGER when: the subject is prose inside a document or README (that is `documentation`), commit
  message wording (`shared/commit-message-rules.md`), a single one-off reply the user just wants rewritten, or
  a subagent's prompt.
allowed-tools: Read, Write, Edit, Glob, Grep, AskUserQuestion, Bash(bash ~/.claude/skills/tune-output/scripts/preflight.sh:*), Bash(bash ~/.claude/skills/tune-output/scripts/ab-run.sh:*), Bash(python ~/.claude/skills/tune-output/scripts/ab-sheet.py:*), Bash(python3 ~/.claude/skills/tune-output/scripts/ab-sheet.py:*), Bash(git check-ignore:*), Bash(git status:*), Bash(gh repo view:*)
---

# Tune output

## Context

- Current state: !`bash ~/.claude/skills/tune-output/scripts/preflight.sh`

## What this skill is for

Response shape is tuned repeatedly and each pass forgets the last one. The cost is not the wasted work — it is
re-adopting a rule that was already measured harmful, or re-arguing a rejection whose reason nobody wrote down.
The ledger is the point of this skill; the harness exists to give the ledger something true to record.

## Process

### 1. Read the ledger before forming any opinion

Read `~/.claude/skills/tune-output/ledger.md` in full. It is short by design.

If the candidate rule — or its near-twin — already has an entry, **say so before proposing anything** and open
with what the last pass concluded. A rule previously rejected is re-opened only with new evidence, and the
entry names what evidence would qualify. Never silently re-adopt something the ledger rejected.

### 2. Locate the rule's home

An output rule can live in four places, and picking the wrong one is the most common failure. Use
**Current state** from Context to see what is configured now, then choose:

| The rule is… | Home |
|---|---|
| how a reply is shaped, always | the output style — `claude/output-styles/<name>.md` |
| a word or phrase never to use | the **Overused Phrases** section of `claude/CLAUDE.md` (it already has the entry-plus-replacement format) |
| a preference with a *why* worth keeping | a `claude/memory/feedback_*.md` file, indexed in CLAUDE.md |
| something a subagent must also obey | `claude/CLAUDE.md` — output styles do not reach Task subagents |

For the verified properties behind that table — what actually reaches the model, what is re-asserted per turn,
which mechanisms fail silently — see `references/mechanisms.md`. Read it before asserting any capability claim
about output styles, `~/.claude/rules/`, or `--append-system-prompt`.

### 3. Audit the candidate against what already exists

For every rule under consideration, assign one verdict and quote the evidence:

- **already-covered** — existing text says substantively the same thing. Quote it. Do not adopt a second copy.
- **partially-covered** — adjacent but narrower or weaker. Quote it and name precisely what is missing.
- **new** — nothing says this. Search before claiming it: `claude/CLAUDE.md` is long and says things in its own
  vocabulary, so grep concepts, not just the candidate's phrasing.
- **contradicted** — existing text says the opposite. This is a decision for the user, never a silent override.

Search `claude/CLAUDE.md`, `claude/memory/*.md` and `claude/skills/*/SKILL.md`. A rule that turns out to be
already-covered is a finding worth reporting, not a failure.

### 4. Hunt conflicts before proposing, not after

A shape rule that reads well in isolation can fight a content rule that matters more. Check the candidate
against at least these, which have collided before:

- **Mandatory reporting** — CLAUDE.md requires every noticed defect be reported. Any rule that deletes,
  truncates or caps content collides here. Splitting and ranking is compatible; dropping is not.
- **Verification** — a rule prescribing the *format* of a success or diagnosis claim must not license
  asserting one that was never observed. Weld the verification requirement on, or reject the rule.
- **Guessed facts** — a rule demanding a specific number obliges the model to produce one even when it cannot
  be known. Ask what unit the model can actually count.
- **Skill procedures** — a numbered list inside a skill is a mandatory checklist. A rule that folds or trims
  steps must be scoped to steps the model authors, never to steps it is executing.

### 5. Test before adopting

Do not ship a shape rule on the strength of it reading well. Run the harness:

```bash
bash ~/.claude/skills/tune-output/scripts/ab-run.sh <candidate-rule.md> <prompts.json> <out-dir>
python ~/.claude/skills/tune-output/scripts/ab-sheet.py <out-dir>
```

Both arms load the user's real global CLAUDE.md, so the result measures what the candidate **adds** to what is
already there. Never run the baseline arm config-less: that measures the candidate against a bare Claude and
flatters it. See `references/ab-harness.md` for the prompt-selection rules, the trap cases, and what the
numbers can and cannot support.

Hand the user the sheet as a `file:///` link and let them call each pair before you read `key.json`. Their read
is the measurement; yours is commentary.

### 6. Apply, then record

Apply the change to the home chosen in step 2. Then append a ledger entry — in the same change, not later.
The entry format is at the top of `ledger.md`. Two fields carry most of the value:

- **Rejected, with reason.** A rejection nobody wrote down gets re-proposed within months.
- **What would re-open it.** A rejection without this reads as permanent, and some are not.

Leave the outcome field blank and marked pending if the user has not yet judged. Never fill in a verdict they
did not give.

## Naming constraint

This repo is **public**. Name and frame every rule for the **behaviour** it produces, never for a
characteristic of the reader. "Action-first responses" is a description of output; anything that describes the
user instead is a personal characterization published into git history, permanently, and cannot be taken back
by a later commit. This applies to the style file, the ledger, and the commit message.

## Out of scope

- Do NOT change commit message format — that is `shared/commit-message-rules.md`.
- Do NOT restyle prose inside documents, READMEs or generated docs — that is `documentation`.
- Do NOT tune subagent or workflow prompts; this skill governs replies to the user.
- Do NOT install a third-party plugin, marketplace entry or hook to carry an output rule. Everything here is
  reachable with a file and a settings key; `references/mechanisms.md` records why the hook route is worse.
- Do NOT edit the style file without a ledger entry in the same change.
