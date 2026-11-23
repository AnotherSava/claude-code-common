"""A project's committed Claude Code settings pin no model.

The user picks the model per session, so a `.claude/settings.json` that names one decides something
that is not the project's to decide. On these machines it also does nothing: the user settings' `env`
block sets `ANTHROPIC_MODEL`, which outranks a project's `model` key at launch
(`learnings/claude-code-model-default-persistence.md`), so the pin reads as a decision while every
session runs the env value. A project `env.ANTHROPIC_MODEL` is the other way to write the same pin,
and outranks the user file's, so it is refused too.

`hooks/model-default-guard.py` keeps the user settings file clear after a `/model` save; it never
looks at a project file, and a pin written by hand or by an agent fires no event at all. The commit
gate sees every write path, which is why the check lives here.

A repo with no `.claude/settings.json` holds. One that is there and will not parse as a JSON object
raises, since whether it pins a model is then unknown.
"""

from __future__ import annotations

import json
import os

REL = ".claude/settings.json"
ENV_KEY = "ANTHROPIC_MODEL"


def check(root: str) -> list[str]:
    """One line per model pin in the project settings file."""
    path = os.path.join(root, REL)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{REL} holds a JSON {type(data).__name__}, not an object, so its keys are unknown")
    violations: list[str] = []
    if "model" in data:
        violations.append(f"{REL} pins `model` to {data['model']!r} — delete the key; the model is picked per session")
    env = data.get("env")
    if isinstance(env, dict) and ENV_KEY in env:
        violations.append(f"{REL} sets env {ENV_KEY}={env[ENV_KEY]!r} — delete it; the model is picked per session")
    return violations
