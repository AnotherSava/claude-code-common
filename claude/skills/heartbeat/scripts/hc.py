#!/usr/bin/env python3
"""healthchecks.io Management API v3 — the operations the `heartbeat` skill needs.

The split between the subcommands is deliberate. A check's ping URL is a CREDENTIAL: anyone
holding it can forge a heartbeat, or silence a real alert by pinging on the job's behalf. So no
subcommand here ever prints one. `upsert` creates or updates a check and reports only its
identity; `store-url` moves the URL straight into a Doppler config over a pipe, so it never
reaches a terminal, a transcript or a shell history.

The API key is per-PROJECT on healthchecks.io — there is no account-wide key — so one key
addresses one project's checks and `list` can only ever audit that project.

Usage:
  hc.py list [--json]
  hc.py upsert --name NAME (--schedule EXPR --tz TZ | --period-seconds N) --grace-seconds N
               [--tags "a b"] [--desc TEXT] [--channels "*"] [--dry-run]
  hc.py store-url --name NAME --doppler-project P --doppler-config C [--key HEARTBEAT_URL]

Exit: 0 ok, 1 API or argument error, 2 the API key could not be read
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

API_ROOT = "https://healthchecks.io/api/v3"
KEY_NAME = "HEALTHCHECKS_API_KEY"
KEY_PROJECT = "tools"
KEY_CONFIG = "prd"

# healthchecks.io's documented bounds for both fields, in seconds. Validated here rather than
# left to the API so a bad value is rejected before it creates a half-configured check.
BOUND_LOW = 60
BOUND_HIGH = 31536000


def api_key() -> str:
    """The key from the environment, else Doppler. Never echoed."""
    key = os.environ.get(KEY_NAME, "").strip()
    if key:
        return key
    try:
        proc = subprocess.run(["doppler", "secrets", "get", KEY_NAME, "--project", KEY_PROJECT,
                               "--config", KEY_CONFIG, "--plain"], capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        sys.exit(f"could not read {KEY_NAME}: doppler is not on PATH, and the variable is unset")
    except subprocess.TimeoutExpired:
        sys.exit(f"could not read {KEY_NAME}: doppler timed out")
    if proc.returncode != 0:
        sys.stderr.write(f"could not read {KEY_NAME} from doppler {KEY_PROJECT}/{KEY_CONFIG}.\n"
                         f"{proc.stderr.strip()}\n"
                         f"Create a READ-WRITE key at healthchecks.io -> Project Settings -> API keys,\n"
                         f"then store it there. It is Claude's own cross-project credential, not an app's.\n")
        sys.exit(2)
    key = proc.stdout.strip()
    if not key:
        sys.exit(2)
    return key


def call(method: str, path: str, key: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API_ROOT}{path}", data=data, method=method,
                                 headers={"X-Api-Key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:400]
        sys.exit(f"healthchecks.io returned HTTP {exc.code} for {method} {path}: {detail}")
    except urllib.error.URLError as exc:
        sys.exit(f"could not reach healthchecks.io: {exc.reason}")


def cmd_list(args: argparse.Namespace) -> int:
    _, payload = call("GET", "/checks/", api_key())
    checks = payload.get("checks", [])
    if args.json:
        # uuid, ping_url and update_url are all stripped: this output goes into a report, and the
        # ping URL is https://hc-ping.com/<uuid>, so the uuid is the same credential in shorter form.
        print(json.dumps([{k: c.get(k) for k in ("name", "slug", "tags", "status", "timeout",
                                                 "grace", "schedule", "tz", "last_ping", "n_pings",
                                                 "channels")}
                          for c in checks], indent=2))
        return 0
    if not checks:
        print("no checks in this healthchecks.io project (the API key addresses one project only)")
        return 0
    width = max(len(c.get("name") or "(unnamed)") for c in checks)
    inert = []
    for c in sorted(checks, key=lambda c: c.get("name") or ""):
        name, cadence = c.get("name") or "(unnamed)", c.get("schedule") or f"every {c.get('timeout')}s"
        print(f"  {name:<{width}}  {c.get('status', '?'):<8} "
              f"{cadence} grace={c.get('grace')}s  last_ping={c.get('last_ping') or 'NEVER'}")
        if not c.get("n_pings"):
            inert.append(f"{name}: NEVER PINGED — sits in `new` forever and can never alert. "
                         f"Nothing is watching this job.")
        if not c.get("channels"):
            inert.append(f"{name}: NO INTEGRATIONS — it can go down, and nobody is told.")
    # Printed after the table, not folded into it: each of these is a check that LOOKS configured and
    # cannot raise an alarm, which is the failure this tool exists to surface.
    for line in inert:
        print(f"  !! {line}")
    if not inert:
        print("  every check above has been pinged at least once and has somewhere to send an alert")
    return 0


def cmd_upsert(args: argparse.Namespace) -> int:
    if not (BOUND_LOW <= args.grace_seconds <= BOUND_HIGH):
        sys.exit(f"--grace-seconds must be {BOUND_LOW}..{BOUND_HIGH}, got {args.grace_seconds}")
    body = {"name": args.name, "grace": args.grace_seconds, "unique": ["name"]}
    # schedule and period are mutually exclusive AT THE API, not merely in this script: when both
    # are sent healthchecks.io saves ONLY the schedule and silently discards the period, so a
    # caller passing both would get a cadence it did not ask for and no error saying so.
    if args.schedule:
        body["schedule"], body["tz"] = args.schedule, args.tz
    else:
        if not (BOUND_LOW <= args.period_seconds <= BOUND_HIGH):
            sys.exit(f"--period-seconds must be {BOUND_LOW}..{BOUND_HIGH}, got {args.period_seconds}")
        body["timeout"] = args.period_seconds
    # channels defaults to "*" (all integrations) because the API's own default is NONE, and a check
    # with no integrations goes red on the dashboard and tells nobody — the silent failure this whole
    # skill exists to prevent, produced by the happy path. Pass --channels '' to opt out deliberately.
    body["channels"] = "*" if args.channels is None else args.channels
    for field, value in (("tags", args.tags), ("desc", args.desc)):
        if value:
            body[field] = value
    if args.dry_run:
        print(json.dumps(body, indent=2))
        return 0
    status, payload = call("POST", "/checks/", api_key(), body)
    verb = "created" if status == 201 else "updated (a check of this name already existed)"
    # Neither ping_url NOR uuid: the ping URL is https://hc-ping.com/<uuid>, so printing the uuid
    # publishes the credential just as surely. The slug is the safe identifier.
    print(f"{verb}: {payload.get('name')}  slug={payload.get('slug') or '(none)'}")
    print(f"integrations assigned: {len(payload.get('channels', '').split(',')) if payload.get('channels') else 0}")
    print("ping URL and uuid deliberately not printed — put the URL in place with `hc.py store-url`")
    return 0


def find_check(name: str, key: str) -> dict:
    _, payload = call("GET", "/checks/", key)
    matches = [c for c in payload.get("checks", []) if c.get("name") == name]
    if not matches:
        sys.exit(f"no check named {name!r} in this project — run `hc.py list` to see what is there")
    if len(matches) > 1:
        sys.exit(f"{len(matches)} checks are named {name!r}; rename them so one name means one job")
    return matches[0]


def cmd_store_url(args: argparse.Namespace) -> int:
    key = api_key()
    check = find_check(args.name, key)
    ping_url = check.get("ping_url")
    if not ping_url:
        sys.exit("the API returned no ping_url — a READ-ONLY key omits it; use a read-write key")
    proc = subprocess.run(["doppler", "secrets", "set", args.key, "--project", args.doppler_project,
                           "--config", args.doppler_config, "--silent"],
                          input=ping_url, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        sys.exit(f"doppler rejected the write: {proc.stderr.strip()}")
    print(f"stored {args.key} in {args.doppler_project}/{args.doppler_config} "
          f"({len(ping_url)} chars, value not shown)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="audit every check this API key can see")
    p_list.add_argument("--json", action="store_true", help="machine-readable, ping URLs stripped")
    p_list.set_defaults(func=cmd_list)

    p_up = sub.add_parser("upsert", help="create a check, or update the one with this name")
    p_up.add_argument("--name", required=True)
    p_up.add_argument("--schedule", help="cron or systemd OnCalendar expression; needs --tz")
    p_up.add_argument("--tz", default="UTC")
    p_up.add_argument("--period-seconds", type=int, default=86400)
    p_up.add_argument("--grace-seconds", type=int, required=True)
    p_up.add_argument("--tags")
    p_up.add_argument("--desc")
    p_up.add_argument("--channels", default=None,
                      help='integrations to notify; defaults to "*" (all). Pass an empty string to '
                           'assign none — the API\'s own default, which alerts nobody')
    p_up.add_argument("--dry-run", action="store_true", help="print the request body, send nothing")
    p_up.set_defaults(func=cmd_upsert)

    p_store = sub.add_parser("store-url", help="pipe a check's ping URL into Doppler, unprinted")
    p_store.add_argument("--name", required=True)
    p_store.add_argument("--doppler-project", required=True)
    p_store.add_argument("--doppler-config", required=True)
    p_store.add_argument("--key", default="HEARTBEAT_URL")
    p_store.set_defaults(func=cmd_store_url)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
