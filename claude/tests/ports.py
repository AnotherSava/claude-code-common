#!/usr/bin/env python3
"""Pin the behaviour of claude/skills/ports/scripts/ports.py, and of the registry it hands out from.

Two things are asserted, and the second is the reason this runs at every commit here rather than only
when the allocator changes:

  the allocator   that it never hands out a number already claimed, already held on this machine, or
                  unusable (the WHATWG blocked set, the privileged range, the ephemeral range), and
                  that it is idempotent on the use case — a deploy script calls it on every run and
                  must get the same answer.
  the registry    that the committed `registry.json` passes its own checker. A duplicate claim there is
                  a port handed to two projects, and the file is edited by hand as often as by the
                  allocator.

The live probe is stubbed. Allocation reads the machine as well as the record, so leaving it real would
make these cases pass or fail on which servers happen to be running.

Usage:  python claude/tests/ports.py
Exit:   0 all cases behave, 1 at least one does not
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PORTS_PATH = REPO / "claude" / "skills" / "ports" / "scripts" / "ports.py"

_spec = importlib.util.spec_from_file_location("ports_skill", PORTS_PATH)
ports = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ports)

REAL_REGISTRY = ports.REGISTRY
REAL_PROBE = ports.port_probe
FAILURES: list[str] = []


class FakeProbe:
    """Stands in for port_probe, with a settable set of ports the machine is holding."""

    WILDCARD = REAL_PROBE.WILDCARD
    Holder = REAL_PROBE.Holder

    def __init__(self, held: set = frozenset()) -> None:
        self.held = set(held)

    def verdict(self, port: int):
        summary = f"port {port} is held" if port in self.held else f"port {port} is free"
        return REAL_PROBE.Verdict(port=port, free=port not in self.held, summary=summary)

    def listeners(self):
        return []

    def port_of(self, holder):
        return REAL_PROBE.port_of(holder)


def check(label: str, got: object, want: object) -> None:
    if got != want:
        FAILURES.append(f"{label}: got {got!r}, want {want!r}")


def run(argv: list, registry: Path) -> tuple:
    """-> (exit code, stdout, stderr) for one CLI invocation against `registry`.

    SystemExit is caught because argparse raises it rather than returning on a usage error, and an
    uncaught one takes the whole suite down mid-run with no report — which is how a case asserting a
    rejected argument once produced an empty pass.
    """
    ports.REGISTRY = registry
    ports.LOCK = registry.with_suffix(".lock")
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ports.main(argv)
        except SystemExit as exit_code:
            code = exit_code.code if isinstance(exit_code.code, int) else 1
    return code, out.getvalue().strip(), err.getvalue().strip()


def seed(directory: str, claims: list) -> Path:
    registry = Path(directory) / "registry.json"
    registry.write_text(json.dumps({"version": 1, "claims": claims}), encoding="utf-8")
    return registry


def claim_for(use_case: str, registry: Path) -> dict:
    """The claim as it is on disk. Written claims are sorted by port, so an index would move under them."""
    claims = json.loads(registry.read_text(encoding="utf-8"))["claims"]
    return next(claim for claim in claims if claim["use_case"] == use_case)


MACHINE = {"scope": "machine", "status": "assigned", "notes": "a claim"}


def main() -> int:
    ports.port_probe = FakeProbe()

    # ---- the committed registry, checked by its own rules --------------------------------------------
    real = json.loads(REAL_REGISTRY.read_text(encoding="utf-8"))
    check("the committed registry has no problems", ports.check_registry(real), [])
    check("the committed registry is version 1", real["version"], ports.VERSION)

    with tempfile.TemporaryDirectory() as directory:
        # ---- allocation ------------------------------------------------------------------------------
        registry = seed(directory, [dict(MACHINE, port=ports.POOL_LOW, use_case="taken", owner="x")])
        code, out, _ = run(["allocate", "--use-case", "fresh", "--owner", "repo", "--notes", "why"], registry)
        check("a new use case gets the lowest free pool port", (code, out), (0, str(ports.POOL_LOW + 1)))

        code, out, _ = run(["allocate", "--use-case", "fresh", "--owner", "repo", "--notes", "why"], registry)
        check("allocating twice returns the same port", (code, out), (0, str(ports.POOL_LOW + 1)))

        code, _, err = run(["allocate", "--use-case", "fresh", "--owner", "repo", "--notes", "why",
                            "--port", str(ports.POOL_HIGH)], registry)
        check("a use case cannot be moved by re-allocating it", code, 1)
        check("and it says which port it already holds", str(ports.POOL_LOW + 1) in err, True)

        # A pin reaching an existing claim is what v15's step 2 does in every repo whose port the registry
        # already assigns, and it used to exit 0 having written nothing.
        code, _, err = run(["allocate", "--use-case", "fresh", "--owner", "repo", "--notes", "why",
                            "--port", str(ports.POOL_LOW + 1), "--pinned", "an outside party"], registry)
        check("a --pinned allocate cannot pin a claim that exists", code, 1)
        check("and it names the command that can", "amend --use-case fresh" in err, True)
        check("the claim is unchanged", "pinned" in claim_for("fresh", registry), False)

        code, _, err = run(["allocate", "--use-case", "other", "--owner", "repo", "--notes", "why",
                            "--port", str(ports.POOL_LOW)], registry)
        check("a claimed port is refused", (code, "taken" in err), (1, True))

        code, _, err = run(["allocate", "--use-case", "blocked", "--owner", "repo", "--notes", "why",
                            "--port", "6000"], registry)
        check("a WHATWG-blocked port needs a reason", (code, "WHATWG" in err), (1, True))
        code, out, _ = run(["allocate", "--use-case", "blocked", "--owner", "repo", "--notes", "why",
                            "--port", "6000", "--pinned", "nothing may listen there"], registry)
        check("and is recorded when it has one", (code, out), (0, "6000"))

        code, _, err = run(["allocate", "--use-case", "elsewhere", "--owner", "x", "--notes", "why",
                            "--scope", "remote"], registry)
        check("a remote claim cannot be auto-assigned", (code, "--port is required" in err), (1, True))

        code, _, err = run(["allocate", "--use-case", "Not_A_Slug", "--owner", "x", "--notes", "why"], registry)
        check("a use case that is not a slug is refused", code, 1)

        # A port the machine holds is stepped over even though no claim records it.
        ports.port_probe = FakeProbe(held={ports.POOL_LOW + 2})
        code, out, err = run(["allocate", "--use-case", "skips-live", "--owner", "repo", "--notes", "why"], registry)
        check("a live port with no claim is skipped", (code, out), (0, str(ports.POOL_LOW + 3)))
        check("and the skip is reported", f"{ports.POOL_LOW + 2}" in err, True)
        ports.port_probe = FakeProbe()

        # ---- amend -----------------------------------------------------------------------------------
        code, out, err = run(["amend", "--use-case", "fresh", "--pinned", "an outside party",
                              "--notes", "a corrected note"], registry)
        check("amend records a pin on an existing claim", (code, out), (0, str(ports.POOL_LOW + 1)))
        check("and writes both fields", (claim_for("fresh", registry)["pinned"],
                                         claim_for("fresh", registry)["notes"]),
              ("an outside party", "a corrected note"))
        check("and says the dotfiles repo is now dirty", "uncommitted change" in err, True)

        code, _, err = run(["amend", "--use-case", "fresh", "--pinned", "an outside party"], registry)
        check("amending to what is already there is not silent", (code, "already says" in err), (0, True))

        code, _, err = run(["amend", "--use-case", "fresh"], registry)
        check("amend with no field to change is refused", (code, "--notes" in err), (1, True))

        code, _, err = run(["amend", "--use-case", "never-recorded", "--notes", "n"], registry)
        check("amending an unknown use case fails", (code, "nothing was amended" in err), (1, True))

        # The whole registry is re-checked before the write, so an amend cannot leave behind a document the
        # gate would then reject in a repo that never ran this command.
        code, _, err = run(["amend", "--use-case", "fresh", "--notes", "   "], registry)
        check("an amend that breaks the registry writes nothing", code, 1)
        check("and the claim keeps what it had", claim_for("fresh", registry)["notes"], "a corrected note")

        code, _, err = run(["amend", "--use-case", "fresh", "--front-for", str(ports.POOL_HIGH - 1)], registry)
        check("a front port with no origin claim is refused by amend too",
              (code, claim_for("fresh", registry).get("front_for")), (1, None))

        # ---- release ---------------------------------------------------------------------------------
        # `--use-case` on get and release as well as allocate: a positional on two of the three made them
        # disagree on how the registry's own key is named.
        code, _, _ = run(["release", "--use-case", "fresh"], registry)
        check("an assigned claim can be released", code, 0)
        check("and the use case is gone", run(["get", "--use-case", "fresh"], registry)[0], 1)
        check("releasing an unknown use case fails", run(["release", "--use-case", "fresh"], registry)[0], 1)
        check("a positional use case is refused, so the three commands cannot drift apart",
              run(["get", "fresh"], registry)[0], 2)

        reserved = seed(directory, [{"port": 5000, "use_case": "os-held", "owner": "macOS", "scope": "machine",
                                     "status": "reserved", "notes": "the OS holds it"}])
        code, _, err = run(["release", "--use-case", "os-held"], reserved)
        check("a reserved claim cannot be released", (code, "5000" in err), (1, True))

        # ---- pool exhaustion -------------------------------------------------------------------------
        full = seed(directory, [dict(MACHINE, port=p, use_case=f"use-{p}", owner="x")
                                for p in range(ports.POOL_LOW, ports.POOL_HIGH + 1)])
        code, _, err = run(["allocate", "--use-case", "overflow", "--owner", "x", "--notes", "why"], full)
        check("an exhausted pool fails rather than reaching outside it", code, 1)
        check("and says where the pool is widened", "ports.py" in err, True)

        # ---- the checker -----------------------------------------------------------------------------
        def problems(claims: list) -> list:
            return ports.check_registry({"version": 1, "claims": claims})

        check("two machine claims on one port are refused",
              len(problems([dict(MACHINE, port=4000, use_case="a", owner="x"),
                            dict(MACHINE, port=4000, use_case="b", owner="y")])), 1)
        check("a machine claim and a container claim may share a number",
              problems([dict(MACHINE, port=3000, use_case="a", owner="x"),
                        {"port": 3000, "use_case": "b", "owner": "y", "scope": "container",
                         "status": "reserved", "notes": "inside its own network"}]), [])
        check("one use case cannot appear twice",
              len(problems([dict(MACHINE, port=4000, use_case="a", owner="x"),
                            dict(MACHINE, port=4001, use_case="a", owner="y")])), 1)
        check("empty notes are refused",
              len(problems([{"port": 4000, "use_case": "a", "owner": "x", "scope": "machine",
                             "status": "assigned", "notes": "  "}])), 1)
        check("an unknown field is refused",
              len(problems([dict(MACHINE, port=4000, use_case="a", owner="x", colour="red")])), 1)
        check("a missing field is refused",
              len(problems([{"port": 4000, "use_case": "a", "scope": "machine", "status": "assigned",
                             "notes": "n"}])), 1)
        check("a front port with no origin claim is refused",
              len(problems([dict(MACHINE, port=4000, use_case="a", owner="x", front_for=4999)])), 1)
        check("a front port whose origin is claimed is fine",
              problems([dict(MACHINE, port=4000, use_case="a", owner="x", front_for=4001),
                        dict(MACHINE, port=4001, use_case="b", owner="x")]), [])
        check("an ephemeral-range claim needs a reason",
              len(problems([dict(MACHINE, port=ports.EPHEMERAL_LOW, use_case="a", owner="x")])), 1)
        check("a bad scope is refused",
              len(problems([{"port": 4000, "use_case": "a", "owner": "x", "scope": "host",
                             "status": "assigned", "notes": "n"}])), 1)

        # ---- the launch-path literal scan, which is what the v15 rule reports ------------------------
        import subprocess

        scan = Path(directory) / "scanned"
        (scan / "web").mkdir(parents=True)
        (scan / "scripts").mkdir()
        subprocess.run(["git", "-C", str(scan), "init", "-q"], check=True)

        def track(rel: str, body: str) -> None:
            (scan / rel).write_text(body, encoding="utf-8")
            subprocess.run(["git", "-C", str(scan), "add", "--", rel], check=True)

        pinned = {"version": 1, "claims": [dict(MACHINE, port=8000, use_case="scanned-dev-server",
                                                owner="scanned", pinned="a URL-restricted token")]}

        track("web/package.json", '{"scripts": {"dev": "node ../scripts/dev.mjs next dev"}}\n')
        check("a dev script with no port literal is clean", ports.check_repo(pinned, scan), ([], []))

        track("README.md", "Open http://localhost:3940 once it is up.\n")
        track("web/.env.example", 'APP_BASE_URL="http://localhost:3940"\n')
        check("prose and env examples are out of scope", ports.check_repo(pinned, scan), ([], []))

        track("scripts/dev.sh", "PORT=8000\n")
        check("a pinned port owned by this repo is allowed", ports.check_repo(pinned, scan), ([], []))

        check("the same literal unpinned is reported",
              len(ports.check_repo({"version": 1, "claims": [dict(MACHINE, port=8000, use_case="scanned-dev-server",
                                                                  owner="scanned")]}, scan)[0]), 1)
        check("a literal pinned to another repo is reported",
              len(ports.check_repo({"version": 1, "claims": [dict(MACHINE, port=8000, use_case="other-thing",
                                                                  owner="elsewhere", pinned="theirs")]}, scan)[0]), 1)

        track("web/package.json", '{"scripts": {"dev": "next dev -p 3940"}}\n')
        found, _ = ports.check_repo(pinned, scan)
        check("a -p flag with no claim is reported", len(found), 1)
        check("and the message names the file and line", "web/package.json:1" in found[0], True)

        # The scan reads what the repo would commit, so staging is not what makes a file count — only a
        # gitignored one is nobody's declaration. `/commit` unstages at skill load before running the
        # gate, so a resolver a migration just added is never in the index when the rule looks.
        (scan / "scripts" / "unstaged.sh").write_text("PORT=4321\n", encoding="utf-8")
        found, _ = ports.check_repo(pinned, scan)
        check("an untracked launch file counts, being on its way into the commit", len(found), 2)
        check("and is named like any other", any("scripts/unstaged.sh:1" in line for line in found), True)
        (scan / "scripts" / "unstaged.sh").unlink()

        (scan / ".gitignore").write_text("/node_modules/\n", encoding="utf-8")
        (scan / "node_modules").mkdir()
        (scan / "node_modules" / "package.json").write_text('{"port": 9999}\n', encoding="utf-8")
        check("a gitignored launch file is nobody's declaration", len(ports.check_repo(pinned, scan)[0]), 1)
        (scan / "node_modules" / "package.json").unlink()

        track("web/package.json", '{"scripts": {"dev": "node ../scripts/dev.mjs next dev"}}\n')
        (scan / "web" / "package.json").write_bytes(b"\xff\xfe\x00{ not text\n")
        try:
            ports.check_repo(pinned, scan)
            FAILURES.append("an unreadable tracked launch file: no raise")
        except RuntimeError as exc:
            check("an unreadable tracked launch file raises", "will not read as text" in str(exc), True)

        # ---- the other half: a port assigned to the repo that nothing here asks for -------------------
        # A literal-free tree, so the half under test is the only thing that can speak. That is the state
        # the first version of this rule called conforming while the port resolved nowhere.
        subprocess.run(["git", "-C", str(scan), "rm", "-q", "--cached", "scripts/dev.sh"], check=True)
        (scan / "scripts" / "dev.sh").unlink()
        track("web/package.json", '{"scripts": {"dev": "next dev"}}\n')
        check("the tree now holds no literal at all", ports.launch_path_literals(scan), [])

        unpinned = {"version": 1, "claims": [dict(MACHINE, port=3950, use_case="scanned-dev-server",
                                                  owner="scanned")]}
        found, _ = ports.check_repo(unpinned, scan)
        check("an unpinned assigned port no file asks for is reported", len(found), 1)
        check("and the message says nothing resolves it", "nothing resolves it" in found[0], True)

        check("a repo the registry assigns nothing owes nothing",
              ports.check_repo({"version": 1, "claims": []}, scan), ([], []))
        check("a pinned port needs no resolver",
              ports.check_repo({"version": 1, "claims": [dict(MACHINE, port=3950, use_case="scanned-dev-server",
                                                              owner="scanned", pinned="an outside party")]},
                               scan), ([], []))
        # A front port is deploy's to allocate at publish time; the repo never names it.
        check("a front_for claim never demands a resolver",
              ports.check_repo({"version": 1, "claims": [dict(MACHINE, port=3950, use_case="scanned-front",
                                                              owner="scanned", front_for=3951),
                                                         dict(MACHINE, port=3951, use_case="scanned-origin",
                                                              owner="scanned", pinned="the origin")]},
                               scan), ([], []))

        # A document naming the tool is not a resolver. Every repo's CLAUDE.md or README carries this
        # sentence once it documents the skill, so counting a marker outside the launch-path files
        # silences the finding on exactly the repos that have started resolving their ports.
        track("CLAUDE.md", "Run `python3 ~/.claude/skills/ports/scripts/ports.py check --repo .` before a commit.\n")
        found, _ = ports.check_repo(unpinned, scan)
        check("a doc naming the tool does not count as a resolver", len(found), 1)

        # Unstaged first, which is the state /commit's `git reset HEAD` probe leaves a migration's new
        # resolver in. Measured in tripit 2026-10-06: v15 step 5 staged it, the probe un-staged it, and the
        # gate then told the reader to copy in a file already sitting in scripts/.
        (scan / "scripts" / "dev.mjs").write_text("import { run } from '.../ports/scripts/dev-port.mjs'\n",
                                                  encoding="utf-8")
        check("an unstaged resolver settles it", ports.check_repo(unpinned, scan), ([], []))

        track("scripts/dev.mjs", "import { run } from '.../ports/scripts/dev-port.mjs'\n")
        check("and so does the same file staged", ports.check_repo(unpinned, scan), ([], []))

        # ---- a port still pinned in the per-machine deploy.env ---------------------------------------
        # Both keys can carry one, and dropping DEV_PORT alone leaves the duplicate a line lower in
        # DEV_CMD, where it overrides the PORT the deploy script exports.
        (scan / "config").mkdir()
        env = scan / "config" / "deploy.env"

        env.write_text("DEV_PORT=3940  # was read here once\n", encoding="utf-8")
        found, notices = ports.check_repo(pinned, scan)
        check("a DEV_PORT still set is a notice, not a problem", (found, len(notices)), ([], 1))
        check("and the notice carries the port, comment stripped", "port 3940 in DEV_PORT" in notices[0], True)

        env.write_text("DEV_CMD=npm run dev -- -p 3939\n", encoding="utf-8")
        found, notices = ports.check_repo(pinned, scan)
        check("a -p hiding in DEV_CMD is reported too", (found, len(notices)), ([], 1))
        check("and names DEV_CMD as the copy that wins", "port 3939 in DEV_CMD" in notices[0], True)

        env.write_text("DEV_PORT=8765\nDEV_CMD=npm run dev -- -p 3939\n", encoding="utf-8")
        check("both keys at once give two notices", len(ports.check_repo(pinned, scan)[1]), 2)

        env.write_text("DEV_CMD=npm run dev\nDEV_PRESTART_CMD=node seed.mjs --count 12\n", encoding="utf-8")
        check("a DEV_CMD with no port is silent", ports.check_repo(pinned, scan), ([], []))

        env.unlink()
        check("an absent deploy.env is the settled state, reported as nothing",
              ports.check_repo(pinned, scan), ([], []))

        # ---- the repo's identity is not whichever directory the caller named -------------------------
        # A pinned claim is what exempts a literal, so getting the owner wrong fabricates a violation
        # against every pinned literal AND drops the genuine finding, at one count and one exit status.
        check("an owner is matched as whole tokens, never as a substring",
              ports._owned_by({"owner": "travel-map"}, "travel"), False)
        check("a repo still matches its own owner",
              ports._owned_by({"owner": "travel-map"}, "travel-map"), True)
        check("a claim several repos share matches each of them and nothing else",
              [ports._owned_by({"owner": "what-is-next, scheduler, printlab"}, n)
               for n in ("what-is-next", "scheduler", "printlab", "what-is")],
              [True, True, True, False])

        ident = Path(directory) / "identity"
        (ident / "scripts").mkdir(parents=True)
        subprocess.run(["git", "-C", str(ident), "init", "-q"], check=True)
        for setting, value in (("user.email", "t@t"), ("user.name", "t")):
            subprocess.run(["git", "-C", str(ident), "config", setting, value], check=True)
        (ident / "scripts" / "dev.sh").write_text("PORT=8000\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(ident), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(ident), "commit", "-qm", "base"], check=True)
        owned = {"version": 1, "claims": [dict(MACHINE, port=8000, use_case="identity-dev-server",
                                               owner="identity", pinned="an outside party")]}
        check("a pinned literal is allowed in the repo that owns it",
              ports.check_repo(owned, ident), ([], []))

        # The case a forked sub-skill hits on every run: same repo, basename no owner matches.
        linked = Path(directory) / "identity-sandbox"
        subprocess.run(["git", "-C", str(ident), "worktree", "add", "--detach", "-q",
                        str(linked), "HEAD"], check=True)
        check("and from a linked worktree, whose own basename matches no owner",
              ports.check_repo(owned, linked), ([], []))
        check("the name comes from the main worktree, not the path given",
              ports._repo_name(linked), "identity")
        subprocess.run(["git", "-C", str(ident), "worktree", "remove", "--force", str(linked)], check=True)

        # A subdirectory is not a repo. Scoping the scan to it misses a resolver sitting above it, so the
        # repo's port reads as one nothing asks for — measured in tripit/web, whose scripts/dev.mjs is at
        # the root. The name alone being right does not fix this; the scan root has to move too.
        subprocess.run(["git", "-C", str(ident), "rm", "-q", "--cached", "scripts/dev.sh"], check=True)
        (ident / "scripts" / "dev.sh").unlink()
        (ident / "web").mkdir()
        (ident / "web" / "package.json").write_text(
            '{"scripts": {"dev": "node ../scripts/dev.mjs next dev"}}\n', encoding="utf-8")
        (ident / "scripts" / "dev.mjs").write_text(
            "import { run } from '.../ports/scripts/dev-port.mjs'\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(ident), "add", "-A"], check=True)
        resolved = {"version": 1, "claims": [dict(MACHINE, port=3951, use_case="identity-dev-server",
                                                  owner="identity")]}
        check("the repo resolves its port at launch", ports.check_repo(resolved, ident), ([], []))
        check("and a subdirectory is judged as the repo containing it",
              ports.check_repo(resolved, ident / "web"), ([], []))

    if FAILURES:
        print(f"ports tests: {len(FAILURES)} case(s) failed\n")
        for failure in FAILURES:
            print(f"  {failure}\n")
        return 1
    print("ports tests: all cases behave")
    return 0


if __name__ == "__main__":
    sys.exit(main())
