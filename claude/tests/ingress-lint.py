#!/usr/bin/env python3
"""Pin the behaviour of claude/scripts/ingress-lint.py.

There were no tests here, which is how the drift this file now guards against stayed invisible: the Caddy
tenancy rules had been reimplemented locally against a reader too weak to feed them, so three ordinary
constructs reached no rule at all and the lint reported clean. Nothing disagreed, because nothing asked.

Two halves, tested differently:

  COMPOSE / upstream rules   this file's own, and asserted directly. They encode a Docker Compose fact and
                             hold on any host.
  TENANCY rules (R1-R7)      landlord's, and NOT reimplemented here. What is asserted is the delegation: that
                             the rules are called for the file `VHOST_SRC` names, skipped in silence for
                             anything else, and reported as NOT CHECKED — never as clean — when the landlord
                             checkout is missing. A stub stands in for landlord so these cases run on a
                             machine that has no checkout at all.

Pure Python, no network, no Docker, no Caddy.

Usage:  python3 claude/tests/ingress-lint.py
Exit:   0 all cases behave, 1 at least one does not
"""

import importlib.util
import os
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LINT_PATH = os.path.join(REPO, "claude", "scripts", "ingress-lint.py")

_spec = importlib.util.spec_from_file_location("ingress_lint", LINT_PATH)
ingress_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ingress_lint)

# A stub landlord. The real rules are landlord's to test (landlord/tests/lint.py); what matters here is that
# this file finds them, calls them with the right arguments, and passes their verdict through unchanged.
STUB_VHOST_LINT = '''\
def lint(path, owns, capabilities):
    if owns is not None or capabilities is not None:
        return [f"{path}:0: STUB — expected owns=None and capabilities=None, got {owns!r}/{capabilities!r}"]
    return [f"{path}:1: STUB VERDICT"]
'''

FAILURES = []


def check(name: str, got, want) -> None:
    if got != want:
        FAILURES.append(f"{name}\n    want: {want!r}\n    got:  {got!r}")


class Tenant:
    """A throwaway repo laid out like a real tenant: a .git, a config/publish.env, and a vhost."""

    def __init__(self, stack, vhost_body: str, vhost_rel: str = "deploy/app.caddy", declare: bool = True,
                 parent: str | None = None):
        # `parent` matters only for the sibling-lookup case, which needs a controlled directory next to the
        # repo. Defaulting to the system temp root there would put a `landlord/` in a shared location.
        self.root = (os.path.join(parent, "repo") if parent
                     else stack.enter_context(tempfile.TemporaryDirectory()))
        os.makedirs(self.root, exist_ok=True)
        os.makedirs(os.path.join(self.root, ".git"), exist_ok=True)
        self.vhost = os.path.join(self.root, vhost_rel)
        os.makedirs(os.path.dirname(self.vhost), exist_ok=True)
        with open(self.vhost, "w", encoding="utf-8") as fh:
            fh.write(vhost_body)
        os.makedirs(os.path.join(self.root, "config"), exist_ok=True)
        with open(os.path.join(self.root, "config", "publish.env"), "w", encoding="utf-8") as fh:
            fh.write("SSH_HOST=box\n")
            if declare:
                fh.write(f"VHOST_SRC={vhost_rel}\n")
            # A value that must never be executed by the reader: sourcing this file would run ssh.
            fh.write('IDENTITY_CHECK=echo "must not run"; exit 9\n')

    def landlord(self, stack) -> str:
        root = stack.enter_context(tempfile.TemporaryDirectory())
        os.makedirs(os.path.join(root, "bin"))
        with open(os.path.join(root, "bin", "vhost-lint.py"), "w", encoding="utf-8") as fh:
            fh.write(STUB_VHOST_LINT)
        return root


# The three constructs the deleted reimplementation could not see. Each is a real violation that its reader
# dropped on the floor; none of them is parsed here any more, so what is asserted is that they reach landlord.
CONTINUED_ADDRESSES = "vancouverprintlab.ca/,\nscheduler.anothersava.com {\n\treverse_proxy printlab-app:3000\n}\n"
HEREDOC_UNMATCHED_BRACE = (
    'scheduler.anothersava.com {\n\trespond <<HTML\n\t<div style="{"\n\tHTML 200\n}\n\n'
    "vancouverprintlab.ca/checkout {\n\treverse_proxy printlab-app:3000\n}\n"
)
ONE_LINE_SNIPPET = "(compress) { encode zstd gzip }\n\nscheduler.anothersava.com {\n\timport compress\n}\n"


def main() -> int:
    import contextlib

    with contextlib.ExitStack() as stack:
        # --- the three constructs now reach the rules -----------------------------------------------------
        for label, body in (
            ("line-continued address list", CONTINUED_ADDRESSES),
            ("heredoc with an unmatched brace", HEREDOC_UNMATCHED_BRACE),
            ("one-line snippet definition", ONE_LINE_SNIPPET),
        ):
            tenant = Tenant(stack, body)
            os.environ["CLAUDE_LANDLORD"] = tenant.landlord(stack)
            problems, notices = ingress_lint.lint_caddy_tenant(tenant.vhost)
            check(f"{label}: reaches landlord's rules", problems, [f"{tenant.vhost}:1: STUB VERDICT"])
            check(f"{label}: no spurious notice", notices, [])

        # --- skip path 1: the file is not this repo's VHOST_SRC --------------------------------------------
        # A standalone Caddyfile drew three false positives from the old local rules. It must now be silent —
        # not "clean with notices", silent, since the tenancy rules simply do not describe it.
        tenant = Tenant(stack, ONE_LINE_SNIPPET, vhost_rel="deploy/app.caddy", declare=False)
        os.environ["CLAUDE_LANDLORD"] = tenant.landlord(stack)
        check("undeclared vhost: no problems", ingress_lint.lint_caddy_tenant(tenant.vhost)[0], [])
        check("undeclared vhost: no notices", ingress_lint.lint_caddy_tenant(tenant.vhost)[1], [])

        tenant = Tenant(stack, ONE_LINE_SNIPPET, vhost_rel="deploy/app.caddy")
        other = os.path.join(tenant.root, "deploy", "unrelated.caddy")
        with open(other, "w", encoding="utf-8") as fh:
            fh.write(ONE_LINE_SNIPPET)
        os.environ["CLAUDE_LANDLORD"] = tenant.landlord(stack)
        check("a different .caddy in the same repo: silent", ingress_lint.lint_caddy_tenant(other), ([], []))

        # --- skip path 2: no landlord checkout -------------------------------------------------------------
        tenant = Tenant(stack, ONE_LINE_SNIPPET)
        os.environ["CLAUDE_LANDLORD"] = os.path.join(tenant.root, "nowhere")
        problems, notices = ingress_lint.lint_caddy_tenant(tenant.vhost)
        check("no landlord: no problems invented", problems, [])
        check("no landlord: exactly one notice", len(notices), 1)
        check("no landlord: notice says NOT CHECKED", "NOT CHECKED" in (notices[0] if notices else ""), True)

        # ...and the notice must survive all the way to the exit status and the printed summary.
        problems, scanned, notices = ingress_lint.lint([tenant.vhost])
        check("no landlord: lint() carries the notice", len(notices), 1)
        check("no landlord: a notice is not a violation", problems, [])
        check("no landlord: the file was still seen", scanned, 1)

        # --- a stale $CLAUDE_LANDLORD must not shadow a real sibling checkout ------------------------------
        parent = stack.enter_context(tempfile.TemporaryDirectory())
        tenant = Tenant(stack, ONE_LINE_SNIPPET, parent=parent)
        os.makedirs(os.path.join(parent, "landlord", "bin"))
        with open(os.path.join(parent, "landlord", "bin", "vhost-lint.py"), "w", encoding="utf-8") as fh:
            fh.write(STUB_VHOST_LINT)
        os.environ["CLAUDE_LANDLORD"] = os.path.join(tenant.root, "nowhere")
        check("stale env var falls back to the sibling",
              ingress_lint.lint_caddy_tenant(tenant.vhost)[0], [f"{tenant.vhost}:1: STUB VERDICT"])

        # --- publish.env is read, never executed ------------------------------------------------------------
        check("publish.env is parsed line-wise",
              ingress_lint._publish_env_value(tenant.root, "VHOST_SRC"), "deploy/app.caddy")
        check("a missing key is None", ingress_lint._publish_env_value(tenant.root, "VHOST_DIR"), None)

        # --- the host layer is still classified out, before any of the above --------------------------------
        tenant = Tenant(stack, "import /etc/caddy/conf.d/*\n", vhost_rel="deploy/base.caddy")
        os.environ["CLAUDE_LANDLORD"] = tenant.landlord(stack)
        check("a conf.d-importing base config is not a tenant", ingress_lint.lint_caddy_tenant(tenant.vhost), ([], []))

        tenant = Tenant(stack, ONE_LINE_SNIPPET, vhost_rel="snippets.d/compress.caddy")
        os.environ["CLAUDE_LANDLORD"] = tenant.landlord(stack)
        check("a snippets.d fragment is not a tenant", ingress_lint.lint_caddy_tenant(tenant.vhost), ([], []))

        # --- the compose half, which is this file's own and unchanged ---------------------------------------
        root = stack.enter_context(tempfile.TemporaryDirectory())
        compose = os.path.join(root, "docker-compose.yml")
        with open(compose, "w", encoding="utf-8") as fh:
            fh.write("services:\n  app:\n    image: x\n    networks: [shared]\n"
                     "networks:\n  shared:\n    external: true\n")
        problems, _ = ingress_lint.lint_compose(compose)
        check("a generic service on a shared network is refused", len(problems), 1)

    if FAILURES:
        print(f"ingress-lint tests: {len(FAILURES)} case(s) failed\n")
        for failure in FAILURES:
            print(f"  {failure}\n")
        return 1
    print("ingress-lint tests: all cases behave")
    return 0


if __name__ == "__main__":
    sys.exit(main())
