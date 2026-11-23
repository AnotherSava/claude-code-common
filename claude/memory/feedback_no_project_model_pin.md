---
name: feedback_no_project_model_pin
description: no project pins a model in its .claude/settings.json; the model is picked per session
metadata:
  type: feedback
---

Do not put a `model` key, or any other model pin, in a project's `.claude/settings.json`.

**Why:** the user picks the model per session. On 2026-11-22 a shepherd project pin to Fable turned up, and the user asked "this pin shouldn't be, should it?". It did nothing anyway: the user settings set `ANTHROPIC_MODEL`, which outranks a project key (`learnings/claude-code-model-default-persistence.md`).

**How to apply:** when a project seems to need a particular model, ask the user. Don't commit a pin. Remove one you find, after asking. From convention v20 the `no-model-pin` rule fails the commit gate of a repo whose `.claude/settings.json` carries `model` or `env.ANTHROPIC_MODEL`; a repo that has not adopted v20 is not checked.
