# Profiling and optimising a skill's cost

A procedural skill can read perfectly and still cost minutes. Measured 2026-09-30, `/commit` took 902 seconds over a five-line memo change in the tauri-dashboard repo and 1081 seconds in this one. Nothing in the harness reports that: the instruments Claude Code ships measure context tokens, and the number that hurts is wall-clock seconds.

**Separate deliberate waiting from cost, and attribute per step, before drawing any conclusion.** In the tauri-dashboard run, 544 of those 902 seconds were two `sleep` calls polling a GitHub Actions run, which `/commit` does by design after the push; the commit itself existed at 294 seconds. Both mistakes available here were made in one sitting — reading the total as the skill's cost, then blaming the sub-skill a coarse segment table happened to name. The per-step table below is what settled it, and it disagreed with the segment table by 4.6× on the step that looked guilty.

## Three costs, and which instrument sees each

A skill spends in three places, and they move independently — trimming one does nothing for the others.

| Cost | Paid | Instrument |
|---|---|---|
| **Always-on listing** — name, `description`, `when_to_use` | Every turn of every session, whether the skill runs or not | `claude plugin details <plugin>`, `/context`, `/skill-doctor` where it is available |
| **On-invoke body** — the SKILL.md text, plus every file and rule it tells Claude to read | Once per invocation, then re-read as cached context on every later turn | `claude plugin details` per-component `on-invoke` column |
| **Wall-clock** — model latency × turns, plus tool time | Once per invocation | Nothing first-party. Read the transcript |

The first two are token accounting and the docs cover them well. The third is the one a user notices, and it is only weakly related to the other two: a 300-word skill that makes forty sequential Bash calls is slower than a 12,000-word one that makes four.

## Measuring a real run

Wall-clock comes from the session transcript, `~/.claude/projects/<slug>/*.jsonl`, where every row carries a timestamp and assistant rows carry a `usage` block. The gap before an assistant row is model latency; the gap before a tool result is tool time. `claude/scripts/profile-skill-run.py` does that arithmetic:

```bash
python3 ~/.claude/scripts/profile-skill-run.py commit                  # this project, newest run
python3 ~/.claude/scripts/profile-skill-run.py commit --project tripit
python3 ~/.claude/scripts/profile-skill-run.py commit --timeline       # every turn
```

It reports total seconds, the model/tool split, turn count, context re-read per turn, a segment per nested sub-skill, and the five longest tool waits — that last line is what distinguishes a slow command from a skill that chose to sleep. The window runs from the invocation to the next instruction the user typed, skipping approvals like `y`, so a session that carries on afterwards does not inflate the total.

**Read the last segment as an upper bound, not as that sub-skill's cost.** A sub-skill's body merges into the same conversation and emits no return marker, so a segment runs until the next sub-skill or the end of the transcript — and the final one also carries whatever the parent did after that sub-skill finished. Attributing a sub-skill's cost exactly needs the `--timeline` view and a human reading where its steps stop.

## Measuring a skill that is not in a plugin

The token side is `claude plugin details`, which needs a plugin. A skill living loose in `~/.claude/skills/` can be measured by copying it into a throwaway plugin layout — the skills must sit under a `skills/` subdirectory, or the inventory reports zero:

```bash
mkdir -p /tmp/probe/skills
cp -R ~/.claude/skills/{commit,reflect,clean-code,docs-relevance} /tmp/probe/skills/
claude --plugin-dir /tmp/probe plugin details probe
```

Against the `/commit` chain on 2026-09-30 that reported an always-on total of ~256 tokens, split as:

| Skill | Always-on | On-invoke |
|---|---|---|
| `commit` | ~40 | ~13.5k |
| `docs-relevance` | ~120 | ~22.8k |
| `reflect` | ~50 | ~4.9k |
| `clean-code` | ~40 | ~1.6k |

So invoking `/commit` costs about 43k tokens of skill body before it has read a single project file, and the chain's always-on share is negligible by comparison. That ratio is the argument for spending effort on the on-invoke side rather than on trimming descriptions.

## What the measurements showed

Two `/commit` runs, both on small changes, profiled 2026-09-30:

| | tauri-dashboard | this repo |
|---|---|---|
| Total | 902s | 1081s |
| Of which deliberate `sleep` | 544s | 0s |
| Model time | 288s (32%) | 621s (57%) |
| Turns | 63 | 91 |
| Context re-read per turn | ~220k tok | ~428k tok |
| Bodies loaded | 262k tok | 334k tok |
| Bash calls | 33 | 30 |

**The segment table is too coarse to prescribe from — attribute per step before changing anything.** Reading the tauri-dashboard run at segment resolution put `/docs-relevance` at 399 seconds. Reading the same run turn by turn, assigning each tool call to the step whose work it does, puts it at 86. The segment number was 4.6× too high because it carried steps 5 through 11 as well, and acting on it would have attacked a step costing a tenth of the run.

Per step, from the `--timeline` view of that run:

| Phase | Seconds | Share |
|---|---|---|
| step 9 CI polling (`sleep 120` + `sleep 420`) | 549.4 | 61% |
| step 4 `/docs-relevance` | 85.7 | 10% |
| step 6 grouping and drafting messages | 41.1 | 5% |
| step 5 confidentiality scan | 40.4 | 4% |
| step 9 stage and commit | 29.1 | 3% |
| step 2 `/reflect` | 25.1 | 3% |
| step 6 project `commit-checks.sh` | 24.3 | 3% |
| steps 10–11 and final report | 22.9 | 3% |
| step 9 push, peer notify, list runs | 21.2 | 2% |
| skill load and step 1 | 17.9 | 2% |
| steps 7–8 validate and present plan | 15.4 | 2% |
| step 3 `/clean-code` | 12.3 | 1% |
| waiting on the user's two approvals | 17.2 | 2% |

One thing dominates and it is not a skill: the CI wait. Set it aside and 358 seconds remain, spread across eleven phases with nothing above 86 seconds — which is the finding that matters, because it means no single step removal fixes this run.

What those eleven phases have in common is reasoning. Of the 358 non-CI seconds, 182 are 17 thinking turns at a mean of 10.7 seconds; 70 are real tool time, 105 is other model output, and 17 is the user typing `y` twice. So past the CI wait, the cost is turns at this context size rather than any step's own work — and the token figures say why: every turn re-reads the whole conversation, so the 91-turn run re-read 39M cached tokens. Adding a turn to a skill that runs late in a long session costs far more than the same turn early.

## Levers, in the order they paid on this run

Each lever carries what it was worth in the 902-second run, so the ordering is measured rather than argued.

1. **Do not block on something external — 549s.** `/commit` spent two `sleep` calls waiting for a GitHub Actions run it had just triggered. Nothing in the remaining steps depended on the outcome, so the wait bought a report that could have arrived later. A step that polls a remote job runs in the background and reports when it exits, or hands the check back as a command.
2. **Spend fewer reasoning turns — 182s of the 358s that remain.** Seventeen thinking turns at a mean of 10.7 seconds, spread across eleven phases, none of them dominant. So this is the lever for everything the CI wait is not, and it is bought by collapsing round trips: independent probes belong in one Bash call, or in a script emitting everything the step needs at once. A script's code never enters context and its output arrives in one turn, which is what makes `scripts/` cheaper than prose.
3. **Do not run the step — 98s.** `/commit` steps 3 and 4 invoked `/clean-code` and `/docs-relevance` unconditionally; only `/reflect` carried a skip condition, and it keys on conversation state rather than on the diff. So `docs-relevance`, the longest SKILL.md in this repo, ran against a commit of two files under `.claude/memos/`. Its own internal conditions gate individual steps and none can decline the whole skill. The gate it was worth is `claude/skills/commit/scripts/change_scope.py`, which classifies the change set and prints a `RUN`/`SKIP` verdict per sub-skill — a script rather than prose, per lever 4. Worth knowing too that the step is a quarter of the non-CI time rather than the headline the segment table made it look.
4. **Move a decision out of the model.** A step whose job is to compare two values, or to decide whether a later step applies, is faster and more reliable as a script printing the verdict. Prose asking Claude to weigh several conditions buys a reasoning turn at whatever the session's context size is — which is lever 2 in its most avoidable form.
5. **Lower reasoning effort for a skill's mechanical stretch.** Effort multiplies every one of those seventeen turns, and staging-and-committing needs none of it. Settings live under `effortLevel` and per-model `modelSettings.<model>.effortLevel`; read what the session actually has before blaming a skill for latency that came from `xhigh`.
6. **Shorten the always-on listing.** This speeds up no run — it reduces what every session carries, and the whole `/commit` chain measures ~256 tokens, so it is the smallest lever here. `claude plugin details` names the worst contributors.

## The parallelism is frontmatter, not plumbing

Before building scan agents under `claude/agents/`, read the SKILL.md frontmatter reference. Four fields already express "run this part in a cheaper model, in parallel, without the main conversation's context", so hand-rolled `Agent` calls and a new install-linked directory buy nothing:

| Field | Effect |
|---|---|
| `context: fork` | Runs the skill in a forked subagent |
| `model` | Sets that subagent's model |
| `effort` | `low` … `max`, overriding the session's level |
| `background` | Defaults to `true`, so forks run concurrently and report when done. Needs 2.1.218+ |
| `user-invocable: false` | Hides it from the `/` menu while leaving it callable by Claude |

**Do not read `context: fork` as a fork of the conversation — it starts fresh.** The docs say so in as many words, and the name invites the opposite reading. The fork gets the skill body and CLAUDE.md, nothing else. That makes it right for a skill whose input is the repository and wrong for one whose input is the conversation: `/reflect` scans the live conversation at its step 3, so it can never be a `context: fork` skill, however appealing its 25 seconds look.

Two consequences worth knowing before turning it on:

- **A forked skill's edits land outside the session's checkpoints, so `/rewind` will not undo them.** Leave every write to the caller — one writer, however many readers. Making the fork proposal-only with `disallowed-tools` is the wrong way to get there where the skill writes files for a living, as `/docs-relevance` does for its screenshot pipeline; give it a writable copy of the change set instead and have it hand back a patch. `~/.claude/learnings/git-sandbox-for-an-uncommitted-change-set.md` carries that mechanism and the approaches that do not work.
- **A backgrounded fork runs with the narrower tool set that applies to background subagents**, and the docs do not enumerate it. Measured 2026-09-30 with a throwaway probe skill — `context: fork`, `background: true`, `effort: low`, invoked once and deleted:

  | Available | Absent |
  |---|---|
  | Bash, Read, Edit, Write, Skill, Agent, ToolSearch | **Grep**, **Glob** |

  Everything else, `WebSearch` and `SendMessage` included, was reachable only through `ToolSearch`. So a skill instructing "use Grep to find …" or "Glob `**/x.py`" silently loses that step in a background fork, while `git grep --untracked` and `git ls-files` survive. Both of `/commit`'s candidates carried exactly one such instruction.

  `Edit` and `Write` being present is the other half of the checkpoint warning above: a fork can write, so proposal-only is a restriction to impose with `disallowed-tools`, never a default to rely on.

- **A fork is not free to start.** That probe did two tool calls and spent 50k tokens and 23 seconds, most of it startup context. Against `/docs-relevance` at 86 seconds that trades well; against `/clean-code` at 12 seconds it does not. Price the startup before forking a cheap step.

- **A completed fork is resumable by name, with its history intact** — which is what makes a feedback loop cheaper than a second scan. `SendMessage` to the skill's name resumes that subagent rather than starting one; the result reports `Resuming agent <name>`. Measured 2026-09-30 with a second throwaway probe: it reported a token from its own first turn and noted that the resuming message had not contained it, so the history was genuinely its own. A completed fork does **not** appear in `ListAgents`, so absence there is not evidence it has gone — address it by name anyway.

Measured on this machine: of `/commit`'s three sub-skills, `/reflect`, `/clean-code` and `/docs-relevance`, none has ever been invoked directly by the user in any transcript, and `/commit` is their only caller — `wrap-up`, `github-pages` and `docs-style` merely name them. That is the evidence for `user-invocable: false` rather than a matter of taste, and `docs-relevance` carries it. The other two do not: `/reflect` is documented as a command to run before `/clear`, in `CLAUDE.md` and in the README, so hiding it needs that documentation changed in the same breath, and `/clean-code` is still a candidate nobody has ruled on.

## Benchmarking a change without paying its side effects

Testing a Context line means running the skill, and running `/commit` commits — the cost problem that `skill-context-evaluator.md` records. Two ways out:

- **A throwaway probe skill.** A skill created mid-session is picked up with no restart and re-read on every invocation, so a minimal skill holding only the lines under test can be invoked once and deleted.
- **`claude plugin eval` with a recorded transcript.** A case's `context.history_file` names a `.jsonl` transcript to resume, and the case's prompt becomes the next user turn — so a real session can be replayed up to the point of invocation. `results.json` carries `durationSeconds` and `costUsd`, and `prompt.md` frontmatter caps a case with `max_turns` and `timeout_seconds`. Graders of type `regex`, `tool_used`, `tool_order` and `file_exists` read the transcript and cost nothing; `llm` and `baseline` call a judge model. Run with `--ablation none` while iterating, since the default runs every case with and without the plugin.

Both routes need the skill reachable as a plugin. The `--plugin-dir` layout above is verified to satisfy `plugin details`; whether `plugin eval` accepts the same inline directory as an ablation target is untested here.

## Availability

Verified on 2.1.251: `claude plugin details`, `claude plugin eval` and `claude plugin validate` are all present in `claude plugin --help`. Secondary write-ups give version floors of 2.1.269 for `eval` — they are wrong, or the floor is older than they say. Check the binary rather than a blog post.

**Do not reach for `/skill-doctor` on this machine.** It is gated behind a feature flag, and `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` blocks the flag fetch, so the command reports `Unknown command` and the `/plugin` **Stats** tab that holds its report stays hidden. That setting is deliberate and stays — `essential-traffic-hides-gated-commands` in this repo's project memory records the decision. The shell subcommands above are unaffected, which makes `claude plugin details` the usable substitute for the context-cost half of what `/skill-doctor` reports. Its docs also say it needs 2.1.252 or later and is unavailable over Remote Control.

The listing budget is governed by `skillListingBudgetFraction` and `skillListingMaxDescChars`; the official docs give 1,536 characters as the per-entry cap and do not publish a default for the fraction. When the listing overflows, Claude Code drops the descriptions of the skills invoked least — so an over-budget listing degrades triggering silently rather than reporting an error.
