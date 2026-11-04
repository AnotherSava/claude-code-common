#!/usr/bin/env python3
"""Write Doppler secrets into named fields of an app's existing JSON settings file.

For an app that keeps its own settings and rewrites them as the user works, so a deploy must set the
secret fields and leave every other value as the app last saved it. An app whose whole config the
project owns renders it from a template instead, which deploy-tauri.sh does without this script.

Usage:  secret_fields.py [--check] <settings.json> <project> <config> <dotted.path=SECRET_NAME>...
        e.g. secret_fields.py "$APPDATA/app/settings.json" whats-next dev platform.token=AGENT_TOKEN

--check does everything but the write, so deploy-tauri.sh can learn that Doppler answers and the settings
file is in place before it stops the running app, and write only once the app is down.

Each value is read with `doppler secrets get --plain` and never printed. An empty value, a missing
file or a path whose parent object is absent fails the whole run before anything is written, so the
file is either fully updated or untouched.
"""

import json
import os
import subprocess
import sys
import tempfile


def secret(name: str, project: str, config: str) -> str:
    result = subprocess.run(["doppler", "secrets", "get", name, "-p", project, "-c", config, "--plain"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"secret_fields: doppler could not read {name} from {project}/{config}: {result.stderr.strip()}")
    value = result.stdout.replace("\r", "").strip()
    if not value:
        sys.exit(f"secret_fields: {name} in {project}/{config} is empty")
    return value


def main() -> int:
    args = sys.argv[1:]
    check_only = bool(args) and args[0] == "--check"
    if check_only:
        args = args[1:]
    if len(args) < 4:
        sys.exit("usage: secret_fields.py [--check] <settings.json> <project> <config> <dotted.path=SECRET_NAME>...")
    path, project, config, pairs = args[0], args[1], args[2], args[3:]
    try:
        with open(path, encoding="utf-8") as handle:
            settings = json.load(handle)
    except FileNotFoundError:
        sys.exit(f"secret_fields: {path} does not exist yet — start the app once so it writes its settings, then deploy again")

    for pair in pairs:
        field, _, name = pair.partition("=")
        if not field or not name:
            sys.exit(f"secret_fields: '{pair}' is not dotted.path=SECRET_NAME")
        *parents, leaf = field.split(".")
        node = settings
        for key in parents:
            if not isinstance(node.get(key), dict):
                sys.exit(f"secret_fields: {path} has no object at '{key}' on the way to {field}")
            node = node[key]
        node[leaf] = secret(name, project, config)
    if check_only:
        return 0

    # Written beside the target and moved over it, so an interrupted run never leaves half a file.
    handle, staged = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        json.dump(settings, out, indent=2)
    os.replace(staged, path)
    print(f"  wrote {', '.join(p.partition('=')[0] for p in pairs)} into {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
