#!/usr/bin/env python3
"""PostModelSwitch: take a saved model or effort default back out of the user settings file.

Enter in the `/model` picker saves the pick as the default for new sessions, where `s` would apply it to
this session only, and the two keys sit next to each other. A misclick on Enter writes `model`, and with
it `modelSettings`, into `~/.claude/settings.json`, which is a symlink into the dotfiles repo, so the
default changes on both machines once the file is committed or synced. The keys are kept out on purpose:
the user picks the effort level from the usage budget left, and the model is pinned by `ANTHROPIC_MODEL`
in the same file's `env` block, which wins over `model` at launch. This hook removes all three keys
(`model`, `modelSettings` and the older `effortLevel`) whenever any of them appears after a switch.

Measured on Claude Code 2.1.322: the save is on disk before this event fires, and rewriting the file
leaves the saving session on its pick and other open sessions where they were. The event does not fire
for an effort-only change, through `/effort` or the effort control inside the `/model` picker, so an
effort save stays in the file until the next model switch runs this.

Registered `async: true`, since the event cannot block and its stdout would become model context; the
script prints nothing. Every decision that writes is logged to `~/.claude/model-default-guard.log`.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

GUARDED = ("model", "modelSettings", "effortLevel")
LOG_PATH = Path.home() / ".claude" / "model-default-guard.log"


def _log(event: str, **data: object) -> None:
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now().astimezone().isoformat(), "event": event, **data}) + "\n")
    except Exception:
        pass


def _settings_path() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    # Written in place at the link's target: a write-and-rename would replace the symlink with a file.
    return Path(os.path.realpath(os.path.join(base, "settings.json")))


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    path = _settings_path()
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except Exception as e:
        _log("read_error", path=str(path), error=repr(e))
        return
    removed = {k: data.pop(k) for k in GUARDED if k in data}
    if not removed:
        return
    try:
        # Claude Code writes this file as two-space JSON with a trailing newline and LF endings on every
        # platform; matching it keeps the diff to the removed keys. newline="\n" stops Windows text mode
        # from writing CRLF.
        with path.open("w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    except Exception as e:
        _log("write_error", path=str(path), error=repr(e))
        return
    _log("removed", path=str(path), removed=removed,
        source=payload.get("source"), to_model=payload.get("to_model"))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _log("error", error=repr(e))
    sys.exit(0)
