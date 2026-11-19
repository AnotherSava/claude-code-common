# What a subagent pays before it reads anything

Every subagent and workflow agent starts with the same preamble, and a review workflow spawns dozens of them, so the
preamble is multiplied by the agent count before any work happens. Most of it is the global `CLAUDE.md`, which
every agent type loads except the built-ins that skip it (Explore, Plan). The tool list costs little.

## Measured

Each figure is the first assistant record's `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`
in the agent's transcript, for an agent told to reply `OK` without calling a tool.

| Date | Setup | Agent type | First request |
|---|---|---|---|
| 2026-11-18 | `CLAUDE.md` 95 KB, skill descriptions ~25K chars | default workflow agent | 69.2k |
| 2026-11-18 | same | `general-purpose` | 69.5k |
| 2026-11-18 | same | `Explore` | 33.9k |
| 2026-11-18 | `CLAUDE.md` 28 KB, descriptions ~16K chars | `general-purpose` | 47.7k |

On the second setup, a 40-agent review-auto run had first requests from 47.4k to 57.3k, median 49.0k.

## What follows

- **A custom `agentType` saves almost nothing.** Custom types still load `CLAUDE.md`. The types that skip it lose
  the rules a reviewer checks against, and Explore reads files in excerpts.
- **Shrink `CLAUDE.md` and the skill listing.** Both reach every agent in every workflow. A workflow's `whenToUse`
  is in the listing too, beside the skill descriptions.
- **Context grows with what each agent reads.** In the same run, the average context per turn was 84.8k, against
  the 49k first request. A prompt that tells every agent to read a whole prepared diff charges that diff to every
  agent.
