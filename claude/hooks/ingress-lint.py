#!/usr/bin/env python3
"""PostToolUse: a compose or Caddy file just written that stakes a generic name on a shared bridge.

On a box where several projects sit behind one reverse proxy, compose publishes a *service's* name as a DNS
alias on every network it joins — so a service called `app` claims `app` on the shared network, and the proxy
resolves whichever container the daemon hands back. That put a commercial storefront on a neighbour's
application for 41 hours: HTTP 200 throughout, healthchecks green, `caddy validate` clean. The same goes for a
vhost dropped into a shared conf.d, where the basename is the only thing keeping tenants apart.

Nothing downstream catches it early. The rules live in `claude/scripts/ingress-lint.py`, which is also what a
repo's `commit-checks.sh` should call; this file is only the adapter that feeds it one changed path. Loaded by
path rather than duplicated, so there is exactly one copy of the rules.

NOT REGISTERED BY DEFAULT. To enable, add to `claude/settings.json` under `PostToolUse` — two entries, because
the `if` field names one tool and one pattern:

    { "matcher": "^(Write|Edit)$", "hooks": [ { "type": "command",
      "if": "Write(//**/docker-compose*.yml)",
      "async": false,
      "command": "python -S \\"$HOME/.claude/hooks/ingress-lint.py\\"" } ] }

...and the same again for `//**/*.caddy` and `//**/Caddyfile`.

Three things that are easy to get wrong, all of which fail silently:

- The `//` root anchor is mandatory. Without it the rule matches nothing and the hook never runs.
- `if` goes INSIDE the hook object, as above. The hooks reference shows it as a sibling of `matcher`; the only
  instance known to work (`skill-tracked.py`, in the live settings) uses the placement above.
- `"async": false` is set EXPLICITLY rather than left to the default, because the default is documented both
  ways — the hooks SKILL.md says `true`, its own reference says `false`. It matters here: this hook reports
  through `additionalContext`, which a backgrounded hook cannot deliver at all, so under the wrong default it
  would fire, find real violations, and say nothing.

Verifying it works therefore needs more than "the hook ran": write a violating compose file and confirm the
violation TEXT reaches the model. A backgrounded hook delivering nothing is indistinguishable from a correctly
silent one.

Silent (exit 0, no output) unless the written file actually violates something. Never raises: a hook that
throws is a hook that breaks every tool call in the session.
"""
import importlib.util
import json
import os
import sys

LINT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "scripts", "ingress-lint.py")
WATCHED_SUFFIXES = (".caddy",)
WATCHED_NAMES = ("Caddyfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")


def watched(path: str) -> bool:
    """Redundant with the `if` gate, and kept: this stays correct if the matcher is ever widened."""
    base = os.path.basename(path)
    return base in WATCHED_NAMES or base.endswith(WATCHED_SUFFIXES)


def load_lint():
    spec = importlib.util.spec_from_file_location("ingress_lint", os.path.normpath(LINT))
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # never break a tool call on a parse hiccup

    tool_input = data.get("tool_input") or {}
    response = data.get("tool_response") or {}
    path = response.get("filePath") or tool_input.get("file_path")
    if not isinstance(path, str) or not watched(path) or not os.path.isfile(path):
        return 0

    try:
        module = load_lint()
        if module is None:
            return 0
        problems, _ = module.lint([path])
    except Exception:
        return 0  # the lint failing is not a reason to disrupt the session

    if not problems:
        return 0

    listed = "\n".join(f"- {p}" for p in problems)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"`ingress-lint` flagged {os.path.basename(path)}. On a host shared with other projects these "
                f"are name collisions waiting to happen, and they fail silently — the wrong app answers with a "
                f"healthy 200. Fix them now:\n{listed}"
            ),
        },
        "suppressOutput": True,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
