---
title: A project's committed Claude Code settings pin no model
rules: no-model-pin
asks: when .claude/settings.json pins a model
---

## What changed

The user picks the model for each session, so no project decides it in its `.claude/settings.json`.
Such a pin is also inert on these machines: the user settings' `env` block sets `ANTHROPIC_MODEL`,
which outranks a project's `model` key at launch, so a folder pinned to one model runs the env value
while its settings say otherwise (`learnings/claude-code-model-default-persistence.md`).

The pin takes two forms, and the rule refuses both: a top-level `model` key, and `ANTHROPIC_MODEL`
inside the file's `env` block. Nothing caught either before. The `/model` guard hook cleans only the
user settings file, and only after a `/model` save; a pin an agent or a person writes into a project
file fires no event.

## Migrating an existing repo

1. **Read `.claude/settings.json`** at the repo root for a top-level `model` key and for
   `ANTHROPIC_MODEL` under `env`.
2. **Ask the user before removing a pin**, naming the value. A pin may record a reason the repo holds
   nowhere else; where the user gives one, write it to a project memory file, so the reason survives
   the key.
3. **Delete the key**, and the `env` block too when that leaves it empty. Leave every other setting
   as it is.
4. **Run the checker** from the repo root, `python ~/.claude/conventions/check.py .`, and confirm
   `no-model-pin` reports nothing.

## When it does not apply

- **No `.claude/settings.json`** at the repo root.
- **The file holds neither key**, settled by reading it in step 1.

## Continuing rule

`no-model-pin`: a repo's `.claude/settings.json` carries no top-level `model` key and no
`env.ANTHROPIC_MODEL`.
