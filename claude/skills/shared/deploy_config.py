#!/usr/bin/env python3
"""A project's deploy settings, read one way for every caller.

    deploy_config.py get <project-root> <KEY>    the value, or nothing when neither file names the key
    deploy_config.py target <DEPLOY_TYPE>        the deploy skill's script for that type; exit 1 for an unknown one
    deploy_config.py types                       every DEPLOY_TYPE, one per line

A project keeps its settings in two files at its root:
  config/deploy.env        committed. What the project decides, the same on every clone: DEPLOY_TYPE, the dev
                           command, the Doppler coordinates, where the app keeps its config.
  config/deploy.local.env  ignored. Only what differs between machines, such as an IDE's install path. Most
                           projects have none.

The deploy targets reach this through `deploy_get` in deploy-config.sh, wrap-up's ship_wrappers.sh through the
same function, `ports.py check` and the deploy-config-committed rule by importing it. It is Python rather than a
shell function because two of those readers are Python, and a second reader of the format is a copy that drifts.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

FILES = ("config/deploy.local.env", "config/deploy.env")

# Every DEPLOY_TYPE `deploy` dispatches, and the script under the deploy skill's scripts/ that each one runs.
TARGETS = {
    "dev-server": "deploy-dev-server.sh",
    "tauri": "deploy-tauri.sh",
    "intellij-plugin": "deploy-intellij-plugin.sh",
    "dotnet": "deploy.sh",
}


def value_in(path: str, key: str) -> Optional[str]:
    """`key`'s value in one settings file, or None when the file is absent or does not name it.

    The value is everything after the first `=`, as a shell `KEY=value` line reads, with a Windows editor's
    carriage return removed, since a trailing \\r survives into a path and fails as "not found".
    """
    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            for line in handle:
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].rstrip("\n").replace("\r", "")
    except FileNotFoundError:
        return None
    return None


def get(root: str, key: str) -> Optional[str]:
    """One setting: the local file's value if it names the key, else the committed file's, else None.

    A key in the local file wins with an empty value too, so a machine can switch off a setting the project
    turns on.
    """
    for relative in FILES:
        value = value_in(os.path.join(root, *relative.split("/")), key)
        if value is not None:
            return value
    return None


def _emit(text: str) -> None:
    # Bytes rather than print(): on Windows a text-mode stdout writes \r\n, and the shell's $(...) keeps the \r.
    sys.stdout.buffer.write(text.encode("utf-8"))


def main(argv: list) -> int:
    if len(argv) == 3 and argv[0] == "get":
        value = get(argv[1], argv[2])
        if value is not None:
            _emit(value + "\n")
        return 0
    if len(argv) == 2 and argv[0] == "target":
        if argv[1] not in TARGETS:
            return 1
        _emit(TARGETS[argv[1]] + "\n")
        return 0
    if argv == ["types"]:
        _emit("".join(f"{name}\n" for name in TARGETS))
        return 0
    print("usage: deploy_config.py get <project-root> <KEY> | target <DEPLOY_TYPE> | types", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
