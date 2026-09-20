---
name: repo-status
description: >-
  Cross-machine status of ONE repo — this machine's clone and the peer's, side by
  side: uncommitted changes, unpushed and inbound commits, branch, age of the
  oldest pending work, convention versions still to adopt, open issues, and a
  one-line description of what each machine is mid-way through. Fetches both
  clones and auto-pulls the clean ones. Prints a short block per machine to the
  terminal, saying only what is not at its default.
  TRIGGER when: user asks "/repo-status", wants to know where a single repo
  stands, "what am I doing in this repo", "is this repo clean on the other
  machine", "does the desktop have unpushed work here", or "is this repo behind
  on conventions".
  DO NOT TRIGGER when: the question is about the fleet rather than one repo (use
  `/github-status`), or a plain `git status` on this machine answers it — this
  skill's reason to exist is the OTHER machine's clone and the columns git has no
  opinion about.
allowed-tools: Bash(python ~/.claude/skills/github-status/scripts/repos-status.py:*), Bash(python3 ~/.claude/skills/github-status/scripts/repos-status.py:*), Bash(test -f ~/.claude/skills/github-status/config/config.env:*), Bash(git -C:*), PowerShell, Read(~/.claude/skills/github-status/config/config.env)
---

## Context
- Config file: !`test -f ~/.claude/skills/github-status/config/config.env && echo PRESENT || echo MISSING`
- This repo: !`git rev-parse --show-toplevel 2>/dev/null || echo NOT-A-REPO`
- Its origin: !`git remote get-url origin 2>/dev/null || echo NO-ORIGIN`

This skill runs the same scanner `/github-status` runs, scoped to one repo with
`--repo`. Everything about how a column is filled, what the cache stores, and how
the peer is reached is defined there — read `~/.claude/skills/github-status/SKILL.md`
when something is not covered below, rather than guessing at it.

## 1. Check the preconditions

- **Config file `MISSING`** — the shared config is `/github-status`'s to create. Say so and
  run that skill's step 1 to write it, then come back. Do not hand-write the file.
- **This repo `NOT-A-REPO` or `NO-ORIGIN`** — there is nothing to report on. Say which of the
  two it is and stop; do not fall back to scanning the fleet.

## 2. Run the scan

```
python ~/.claude/skills/github-status/scripts/repos-status.py --repo .
```

Use `python3` on macOS and Linux. Width resolves exactly as in `/github-status` step 2 —
pass nothing here; on Windows get the console width from the **PowerShell tool** evaluating
`$Host.UI.RawUI.WindowSize.Width`, subtract 2, and pass `--width <N>`.

To ask about a repo you are not standing in, pass its path or its `OWNER/REPO` slug instead
of `.`. A path is resolved to its slug here, so the peer finds its own clone whatever it
calls the folder.

The output is **not** the fleet table. One repo gets a short block per machine:

```
claude — AnotherSava/claude-code-common

  air     6 uncommitted (+360/-29) · oldest 9h ago
  chrome  clean
```

Four things follow from that shape:

- **Every fact at its default is left out**, because someone asking about this repo wants
  what is not ordinary. Unsaid means `main`, an upstream level in both directions, a current
  convention record, and zero open issues. A machine with none of them reads `clean`, and that
  word is the whole line — never an empty one.
- **What is not ordinary is always said**: a branch as `on <branch>`, then the uncommitted
  count with its line diff, `N unpushed`, `N inbound` (`(pulled)` when the auto-pull took
  them), the age of the oldest pending work, and the convention gap. A machine that was not
  reached says so with its error; one with no clone says `no clone here`.
- **Unknown is distinguished from zero.** `gh` failing to answer prints `open issues unknown`
  in the title rather than nothing, which would assert a zero nobody checked.
- **Nothing is written but the terminal** — no HTML for one repo. The only file is a state
  file under the repo's own name, which `--report` reads; `--html` is refused, not ignored.

A repo found on no machine exits 2 naming the reason, so an empty block is impossible.

The detail sections below the block — porcelain and unpushed listings — are raw material for
step 3, not part of what you hand over.

## 3. Write the descriptions and render

Identical to `/github-status` step 3, and its rules apply verbatim — one line per machine
marked `<analyze below>`, ≤ ~80 chars, describing the work and not the counts, the branch,
the issue total, the convention gap or the machine's own name. A cell that arrived filled
came from the cache; leave it alone.

```
python ~/.claude/skills/github-status/scripts/repos-status.py --repo . --report <<'JSON'
{"<PROJECT cell>": "<one-line summary>"}
JSON
```

Key by the repo's name as the block's title shows it, before any ` — ` slug. Both machines
working means an object keyed by machine name, as in `/github-status`. **Pass `--repo`
again** — it is what points `--report` at this repo's state file rather than the fleet's.

A written description prints under its machine's line, wrapped and indented to it. When
neither machine is owed one, step 2's block is already final — hand it over and skip
`--report` entirely.

The description cache is shared with `/github-status` and **merged, not replaced**, on both
machines: this run saw one repo, so it overwrites that repo's entry and carries every other
one through. Do not pass `--cache` to "isolate" the run — a separate cache would make the
next fleet run re-read work already described.

## 4. Hand it over

One thing: the block, pasted verbatim inside a fenced code block, from `--report` if it ran
and otherwise from step 2. It is already aligned and wrapped — do not hand-draw it, reorder
it, or expand the facts it deliberately left out. Do not paste the detail sections.

The block is terse by design, so a sentence above it is usually worth writing — what the
shape of it means, rather than a reading of each line back. When every machine says `clean`,
that sentence is the answer and the block is the evidence for it.

## Out of scope
- Do NOT push, commit, stash, merge, rebase, or check out anything, on either machine. As in
  `/github-status`, the only content mutations are `git fetch` and `git pull --ff-only` on a
  clean clone.
- Do NOT run `/adopt` off the back of the CONV number, or any step's `apply`. The column
  states a gap; closing one is a walk through that repo's own session.
- Do NOT widen the run to other repos. A question about the fleet is `/github-status`, which
  reuses this scan unscoped — running this skill repeatedly over several repos pays the peer
  SSH hop once per repo for a report that one fleet run already produces.
