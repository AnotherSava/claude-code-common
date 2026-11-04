#!/usr/bin/env python3
"""The deploy settings resolve the same way for every target, and `deploy` reaches the right one.

`shared/deploy-config.sh` reads a project's committed config/deploy.env with an ignored
config/deploy.local.env over it, and `deploy/scripts/run.sh` dispatches on the DEPLOY_TYPE it finds.
Every deploy target and the cleanup script read through the first, and the `deploy` shell function
enters through the second, so a defect in either reaches every project on both machines.

  local-wins      a key in the local file beats the committed one, an empty value included
  committed       a key only the committed file names is read from it
  absent          a key neither names reads as empty, with exit 0
  crlf            a value saved by a Windows editor loses its trailing carriage return
  expand          %APP_CONFIG% and its %APPDATA% alias become the same per-OS directory
  install-dir     INSTALL_DIR wins when set, and the per-OS default applies when it is not
  legacy          a repo below convention 017 runs its own scripts/deploy.sh with the arguments
  legacy-none     a repo below 017 with no wrapper dispatches on DEPLOY_TYPE like an adopted one
  declined        a fork whose record declines 017 runs its wrapper, though its number is above 17
  dispatch        a repo at 017 reaches the target DEPLOY_TYPE names
  no-type         a missing DEPLOY_TYPE stops with a message naming the key
  unknown-type    an unknown DEPLOY_TYPE stops with a message naming the value
  unconfigured    a directory with no config/deploy.env above it is told to run /deploy
  secret-fields   secret_fields.py sets each named field from Doppler and leaves every other value as it was
  secret-empty    an empty secret fails the run and leaves the settings file untouched
  secret-check    --check reads every secret and writes nothing, and fails where a write would

Usage:  python claude/tests/deploy-config.py
Exit:   0 all hold, 1 one does not or the run could not be set up
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HELPER = os.path.join(REPO, "claude", "skills", "shared", "deploy-config.sh")
RUN = os.path.join(REPO, "claude", "skills", "deploy", "scripts", "run.sh")
SECRET_FIELDS = os.path.join(REPO, "claude", "skills", "deploy", "scripts", "secret_fields.py")

# Stands in for `doppler secrets get NAME -p P -c C --plain`: prints value-of-NAME, or nothing for EMPTY.
FAKE_DOPPLER = """import sys
name = sys.argv[3]
print("" if name == "EMPTY" else f"value-of-{name}")
"""

FAILURES = []


def check(name: str, got: str, want: str) -> None:
    if got != want:
        FAILURES.append(f"{name}: expected {want!r}, got {got!r}")


def write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def helper(bash: str, project: str, expression: str, env: dict | None = None) -> str:
    """Source the helper from `project` and print what `expression` prints."""
    result = subprocess.run([bash, "-c", f'source "$1"; {expression}', "_", HELPER], cwd=project,
                            capture_output=True, text=True, env=env)
    if result.returncode != 0:
        FAILURES.append(f"helper exited {result.returncode} for {expression!r}: {result.stderr.strip()}")
    return result.stdout.rstrip("\n")


def git_repo(path: str) -> None:
    """Make `path` a repo the conventions govern: run.sh asks the engine, which answers only for one."""
    os.makedirs(path, exist_ok=True)
    subprocess.run(["git", "init", "-q", path], check=True)


def deploy(bash: str, project: str, *args: str) -> tuple[int, str]:
    result = subprocess.run([bash, RUN, *args], cwd=project, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return result.returncode, result.stdout + result.stderr


def secret_fields(scratch: str) -> None:
    bin_dir = os.path.join(scratch, "bin")
    write(os.path.join(bin_dir, "fake_doppler.py"), FAKE_DOPPLER)
    if os.name == "nt":
        write(os.path.join(bin_dir, "doppler.cmd"), f'@"{sys.executable}" "%~dp0fake_doppler.py" %*\n')
    else:
        write(os.path.join(bin_dir, "doppler"), f'#!/bin/sh\nexec "{sys.executable}" "$(dirname "$0")/fake_doppler.py" "$@"\n')
        os.chmod(os.path.join(bin_dir, "doppler"), 0o755)
    env = dict(os.environ, PATH=bin_dir + os.pathsep + os.environ["PATH"])
    settings = os.path.join(scratch, "settings.json")
    original = {"platform": {"token": "old", "url": "https://keep"}, "plex": {"token": "old"}, "theme": "dark"}
    write(settings, json.dumps(original))

    def run(*pairs: str, flags: tuple = ()) -> int:
        return subprocess.run([sys.executable, SECRET_FIELDS, *flags, settings, "proj", "cfg", *pairs], env=env,
                              capture_output=True, text=True).returncode

    code = run("platform.token=AGENT_TOKEN", "plex.token=PLEX_TOKEN")
    with open(settings, encoding="utf-8") as handle:
        got = json.load(handle)
    want = {"platform": {"token": "value-of-AGENT_TOKEN", "url": "https://keep"},
            "plex": {"token": "value-of-PLEX_TOKEN"}, "theme": "dark"}
    check("secret-fields", f"{code} {json.dumps(got, sort_keys=True)}", f"0 {json.dumps(want, sort_keys=True)}")

    code = run("platform.token=CHANGED", "plex.token=EMPTY")
    with open(settings, encoding="utf-8") as handle:
        after = json.load(handle)
    check("secret-empty", f"{code != 0} {json.dumps(after, sort_keys=True)}", f"True {json.dumps(want, sort_keys=True)}")

    passed, failed = run("platform.token=CHANGED", flags=("--check",)), run("plex.token=EMPTY", flags=("--check",))
    with open(settings, encoding="utf-8") as handle:
        after = json.load(handle)
    check("secret-check", f"{passed} {failed != 0} {json.dumps(after, sort_keys=True)}", f"0 True {json.dumps(want, sort_keys=True)}")


def main() -> int:
    bash = shutil.which("bash")
    if not bash:
        print("deploy config: NOT RUN — no bash on PATH")
        return 1
    scratch = tempfile.mkdtemp(prefix="deploy-config-test.")
    try:
        project = os.path.join(scratch, "proj")
        write(os.path.join(project, "config", "deploy.env"),
              "DEPLOY_TYPE=dev-server\nDEV_DIR=web\nDEV_CMD=npm run dev\r\nDEV_TAILNET=no\n")
        write(os.path.join(project, "config", "deploy.local.env"), "DEV_DIR=site\nDEV_TAILNET=\n")
        os.makedirs(os.path.join(project, "web"))

        check("local-wins", helper(bash, project, "deploy_get DEV_DIR"), "site")
        check("local-wins (empty)", helper(bash, project, "deploy_get DEV_TAILNET"), "")
        check("committed", helper(bash, project, "deploy_get DEPLOY_TYPE"), "dev-server")
        check("absent", helper(bash, project, "deploy_get NO_SUCH_KEY"), "")
        check("crlf", helper(bash, project, "deploy_get DEV_CMD"), "npm run dev")

        env = dict(os.environ, APPDATA="C:/Users/x/AppData/Roaming")
        canonical = helper(bash, project, 'deploy_expand "%APP_CONFIG%/app/config.json"', env)
        check("expand (alias)", helper(bash, project, 'deploy_expand "%APPDATA%/app/config.json"', env), canonical)
        if "%" in canonical or not canonical.endswith("/app/config.json"):
            FAILURES.append(f"expand: %APP_CONFIG% was not replaced: {canonical!r}")

        os_name = helper(bash, project, "echo $DEPLOY_OS")
        default = {"mac": "/Applications", "win": "C:/Programs/myapp"}.get(os_name)
        if default:
            check("install-dir default", helper(bash, project, "deploy_install_dir myapp"), default)
        write(os.path.join(project, "config", "deploy.local.env"), "INSTALL_DIR=%APP_CONFIG%/plugins\n")
        check("install-dir set", helper(bash, project, "deploy_install_dir myapp", env),
              helper(bash, project, 'deploy_expand "%APP_CONFIG%/plugins"', env))

        legacy = os.path.join(scratch, "legacy")
        git_repo(legacy)
        write(os.path.join(legacy, "config", "deploy.env"), "INSTALL_DIR=/tmp/x\n")
        write(os.path.join(legacy, ".claude", "conventions"), "# header\n16\n")
        write(os.path.join(legacy, "scripts", "deploy.sh"), 'echo "wrapper ran with: $*"\n')
        code, out = deploy(bash, os.path.join(legacy, "config"), "0")
        check("legacy", f"{code} {out.strip()}", "0 wrapper ran with: 0")
        os.remove(os.path.join(legacy, "scripts", "deploy.sh"))
        write(os.path.join(legacy, "config", "deploy.env"), "DEPLOY_TYPE=dev-server\n")
        code, out = deploy(bash, legacy, "--bogus")
        if code == 0 or "deploy takes only --db" not in out:
            FAILURES.append(f"legacy-none: expected the dev-server target to reject --bogus, got {code}: {out.strip()}")

        declined = os.path.join(scratch, "declined")
        git_repo(declined)
        write(os.path.join(declined, "config", "deploy.env"), "DEPLOY_TYPE=dev-server\n")
        write(os.path.join(declined, ".claude", "conventions"), "18\ndecline 17 tracks an upstream project\n")
        write(os.path.join(declined, "scripts", "deploy.sh"), 'echo "wrapper ran with: $*"\n')
        code, out = deploy(bash, declined, "0")
        check("declined", f"{code} {out.strip()}", "0 wrapper ran with: 0")

        current = os.path.join(scratch, "current")
        git_repo(current)
        write(os.path.join(current, ".claude", "conventions"), "17\n")
        write(os.path.join(current, "config", "deploy.env"), "DEPLOY_TYPE=dev-server\n")
        code, out = deploy(bash, current, "--bogus")
        if code == 0 or "deploy takes only --db" not in out:
            FAILURES.append(f"dispatch: dev-server should have rejected --bogus, got {code}: {out.strip()}")
        write(os.path.join(current, "config", "deploy.env"), "DEV_DIR=.\n")
        code, out = deploy(bash, current)
        if code == 0 or "DEPLOY_TYPE" not in out:
            FAILURES.append(f"no-type: expected a failure naming DEPLOY_TYPE, got {code}: {out.strip()}")
        write(os.path.join(current, "config", "deploy.env"), "DEPLOY_TYPE=rocket\n")
        code, out = deploy(bash, current)
        if code == 0 or "rocket" not in out:
            FAILURES.append(f"unknown-type: expected a failure naming rocket, got {code}: {out.strip()}")

        bare = os.path.join(scratch, "bare")
        os.makedirs(bare)
        code, out = deploy(bash, bare)
        if code == 0 or "/deploy" not in out:
            FAILURES.append(f"unconfigured: expected a failure naming /deploy, got {code}: {out.strip()}")

        secret_fields(scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if FAILURES:
        print(f"deploy config: {len(FAILURES)} failure(s)\n")
        for failure in FAILURES:
            print(f"  {failure}")
        return 1
    print("deploy config: local file wins, placeholders and defaults resolve, run.sh dispatches by type and version, secret fields write whole or not at all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
