# The A/B harness

Two scripts and a JSON file. `ab-run.sh` generates both arms; `ab-sheet.py` renders them side by side with the
sides shuffled per pair and the mapping written where nobody reads it until after judging.

## What it measures, and what it cannot

It measures **prose shape**: how a reply reads. Tools are disabled in both arms, so it says nothing about rules
that only fire while Claude is executing — precedence between a shape rule and a harness requirement, or
whether a checklist carries state instead of prose. Those have to be judged by living with them, and the
report must say so rather than letting a prose result stand in for the whole question.

## `--tools ""` does not disable tools

It is silently ignored. A run using it reaches every MCP server the user has configured, and the first run of
this harness did exactly that: one arm answered a VPS login question by searching the user's Gmail and
quoting real provisioning emails, while the other answered from the prompt alone. That is not a comparison of
prose shape — it is a comparison of who happened to do research — and it read the user's private mail without
anyone intending it.

The failure is invisible unless a response happens to cite something it could only have fetched. Nothing warns,
both arms complete, and the sheet looks normal.

What works, verified behaviourally rather than from the flag's name:

```
--strict-mcp-config --disallowed-tools WebSearch WebFetch Bash
```

`--restricted` also drops MCP servers, but it ignores user settings files and takes the global CLAUDE.md with
them — which destroys the baseline this harness exists to preserve. File tools stay enabled and are harmless,
because the scratch working directory is empty.

## Flags alone cannot isolate this. Do it in the prompt

Four configurations were tried and all four leaked:

| tried | what happened |
|---|---|
| `--tools ""` | silently ignored; every MCP server live |
| `--tools TodoWrite` (as an allowlist) | did not restrict; Read, Edit, Bash, PowerShell all still available |
| `--strict-mcp-config --disallowed-tools WebSearch WebFetch Bash` | MCP gone, but `Agent`, `Read`, `Glob`, `Grep` stayed — responses spawned background subagents, hit the 600s print ceiling and were captured mid-flight as preambles, and one read the user's real `.gitignore` and project memory |
| `--restricted --strict-mcp-config` | drops MCP and command-running tools, but its own help says it removes only those and WebFetch — `Agent` and the file tools stay. It also ignores user settings files, taking the global CLAUDE.md with them |

The lesson is that these prompts are *tasks* to an agentic CLI, and no flag reliably turns that off. Constrain
it in the prompt instead. `ab-run.sh` prepends this to **both** arms, identically:

> Answer directly, from what you already know. Do not use any tools, do not read or search any files, do not
> search the web, and do not spawn subagents. Treat this as a question to answer in one reply, not a task to
> execute.

Identical text in both arms cannot bias the comparison, and it constrains where the answer comes *from* while
saying nothing about how it is *shaped*. Keep `--strict-mcp-config` as well — belt and braces, and it costs
nothing.

**Verify the isolation held rather than trusting any of it.** Before judging a run, grep the arms for
`Background tasks still running`, `Research is running`, and any reference to a real path or file the prompt
did not contain. A run that leaks is void, and it looks completely normal in the sheet.

Smoke-test on a cheap model first (`AB_MODEL=haiku`). A full Opus pass is roughly 25 minutes; discovering a
leak after one is the expensive way to learn the flags did not hold.

**Pass all three arguments as absolute paths, and read the runner's exit status.** The Bash working directory
persists between calls, so a `cd` into a previous run's output directory silently re-roots every relative
path after it — including the path to the runner itself. That happened here: the invocation died with
`No such file or directory`, the pipe to `tail` discarded the non-zero status so it reported success, and the
next command read the *previous* run's files and presented them as the new results. A run that never started
must not be able to look like one that finished.

Both arms load the user's real global CLAUDE.md. This is the single most important setting and the easiest to
get wrong: dropping user config from the baseline compares the candidate against a bare, unconfigured Claude,
which flatters any style rule and answers a question nobody asked. The question is what the candidate **adds**
to the rules already in force.

The working directory is a fresh scratch dir outside every repo, so no project CLAUDE.md and no git status
reach either arm.

## Choosing prompts

Pull them from the user's own transcripts (`~/.claude/projects/<slug>/*.jsonl`), not from imagination. Real
prompts carry the user's actual phrasing, typos included; invented eval cases drift toward the shape the rule
was written for and quietly confirm it.

Most real prompts reference a file, a screenshot or a prior turn and are unusable as-is. Prepend the minimum
context inline so a standalone answer is meaningful, and record what was changed. Keep the user's voice.

Never let a prompt mention formatting, brevity, style or the hypothesis. That leaks it into both arms.

**The case set cannot be committed to this repo.** Prompts faithful enough to be worth testing on carry the
things that make them faithful — host addresses, backup repository sizes and schedules, tailnet setup, which
machine holds what. None of it looks like a credential, which is exactly why it reads as safe to commit, and
this repo is public. Keep the case set in the gitignored scratch directory and let each pass rebuild it. That
costs the ability to compare results across passes; record in the ledger which genres were covered instead,
since the genre list is the reusable part and the prompts are not.

**Cover the genres where the rule should show an effect *or a regression*:**

| genre | probes |
|---|---|
| progress-report | the largest measured effect of shape rules |
| error-report | the largest effect, and the largest known regression |
| options | that a shape rule does not eat the answer |
| explain | that an explicit request for depth still gets depth |
| how-to | step structure |
| completion-report | whether a success claim stays honest |
| enumeration | that a long list gets split, not truncated |
| direct-answer | that a one-line answer stays one line |

## Build in traps

A preference test cannot catch a regression, because both arms will look fine. Two trap shapes have caught
real harm:

- **An under-determined failure.** Paste output that genuinely does not identify a cause. A rule that
  prescribes "state cause and fix" pressures the model into naming a plausible one. That is how the upstream
  ruleset's only consistent regression was produced, and it is exactly the failure mode the repo's own
  evidence rules exist to stop.
- **A completion report where some items only look verified.** A timer that is `active` but has never fired,
  an import attested only by its own stdout. Any answer that says "done" is wrong, and a shape rule that
  rewards visible wins is what makes that answer tempting.

## Reading the result

The user reads the pairs blind and calls each one. That is the measurement. Do not read `key.json` first and
do not offer a preferred side before they have called it.

Two failure modes when interpreting:

- **A word count is not a verdict.** A shorter answer that dropped an item is worse, not better. Check whether
  a shrunken list was split or truncated.
- **An aggregate hides its own shape.** If most of the movement comes from two cases, the honest claim is
  about those two genres, not about responses in general. Say which cases moved and which did not.

Adopt on a clear majority, not a bare one. A 5-3 split is noise; it means the rule is not doing much, which is
itself a result worth recording.

## What was deliberately left out

The upstream harness this was distilled from carried an LLM judge, a three-condition vocabulary, per-condition
budget enforcement, retry with backoff, resumable JSONL, pairing validation and a release gate — roughly 1400
lines including its own tests. At eight pairs a person can simply read them, and every one of those parts is
apparatus around a task that runs a few times a year.

Two of its defects are worth not reproducing: its judging pass was completely unmetered while generation was
capped, and its published results were not reproducible because the raw rows were gitignored. If a result is
worth recording, keep the prompts and the responses, not the runner.
