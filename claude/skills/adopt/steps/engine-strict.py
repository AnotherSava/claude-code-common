#!/usr/bin/env python3
"""v8 — a declared Node range is enforced by npm rather than merely advertised.

npm reads `engines` and then installs anyway: the range is advisory, so it prints a warning
into a wall of install output and carries on. A project can therefore have its
`engines.node`, its `.nvmrc` and its base image all agreeing while somebody quietly builds
on another runtime, and the failure surfaces far from its cause — one such install of a
Node-22 project under Node 24 presented as 245 unrelated-looking TypeScript errors, not as
a version complaint. Setting `engine-strict=true` in the `.npmrc` beside the manifest turns
that into `EBADENGINE`, which stops the install.

    engine-strict.py probe  <repo-root>              0 applies · 1 no · 2 ask · 3 error
    engine-strict.py apply  <repo-root> [--dry-run]  0 done · 3 stopped, nothing written
    engine-strict.py verify <repo-root>              0 in shape · 2 unobservable · 3 not

Only a manifest that declares `engines.node` is in scope, because a project declaring no
range has nothing for npm to enforce. That is what makes this step's order behind v7 a
dependency rather than a preference: a repo walked here first records that it has no range,
and v7 gives it one a minute later.

The `.npmrc` this step reads and writes is the one beside `package.json` and never one
higher up the tree. npm resolves the project config from the directory that holds the
manifest, so a file at a repo root is not read at all when npm runs in `web/`.
"""

import os
import re
import sys
from typing import NamedTuple

# sys.path[0] is already this directory when the engine runs the script by path; the insert is
# for a caller that reaches it another way, and it mirrors how v1 reaches the memo skill's module.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _dispatch  # noqa: E402  — path set above
import node_manifests as nm  # noqa: E402  — path set above, as v1 does for the memo skill

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NPMRC = ".npmrc"
KEY = "engine-strict"
SETTING = f"{KEY}=true"
COMMENT = ("# npm treats `engines` as advisory by default — it warns and installs anyway, so the range in",
           "# package.json, the .nvmrc beside it and whatever CI installs can all agree while someone quietly",
           "# builds on another runtime. This turns that silent mis-install into EBADENGINE. The failure it",
           "# prevents surfaces far from its cause: one wrong-runtime install read as 245 unrelated-looking",
           "# type errors rather than as a version mismatch.")
# An .npmrc line is `key = value` in ini form. A line whose first non-space character opens a
# comment is skipped; everything else has to hold an `=` or this step does not know what it is.
ASSIGNMENT_RE = re.compile(r"^\s*([A-Za-z0-9_.@/-]+)\s*=\s*(.*?)\s*$")


class Finding(NamedTuple):
    rel: str      # the manifest, repo-relative
    npmrc: str    # its sibling .npmrc, repo-relative, whether or not it exists
    state: str    # "conformant" · "missing" · "opted-out" · "unreadable"
    detail: str


def strict_value(text: str | None) -> str | None:
    """The last value `.npmrc` assigns to engine-strict, or None when it assigns none.

    The last assignment is the effective one, as it is for every ini file npm reads, so a
    file that sets the key twice is answered the way npm would answer it rather than by
    whichever line this reader saw first.
    """
    found = None
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped[0] in ";#":
            continue
        match = ASSIGNMENT_RE.match(stripped)
        if match and match.group(1).casefold() == KEY:
            found = match.group(2).strip().strip("\"'").casefold()
    return found


def declares_range(manifest: nm.Manifest) -> bool:
    engines = manifest.data.get("engines")
    node = engines.get("node") if isinstance(engines, dict) else None
    return isinstance(node, str) and bool(node.strip())


def survey(root: str) -> tuple[list[Finding], list[str], int]:
    """Every manifest that declares a range, classified; the unreadable ones; the total seen."""
    findings: list[Finding] = []
    unreadable: list[str] = []
    total = 0
    for manifest in nm.read_all(root):
        if manifest.error:
            unreadable.append(manifest.error)
            continue
        total += 1
        if not declares_range(manifest):
            continue
        npmrc_rel = nm.sibling(manifest.rel, NPMRC)
        exists = os.path.isfile(os.path.join(root, *npmrc_rel.split("/")))
        text = nm.read_text(root, npmrc_rel)
        if exists and text is None:
            findings.append(Finding(manifest.rel, npmrc_rel, "unreadable", f"{npmrc_rel} is there and could not be read"))
            continue
        value = strict_value(text)
        if value == "true":
            findings.append(Finding(manifest.rel, npmrc_rel, "conformant", f"{npmrc_rel} sets {SETTING}"))
        elif value is None:
            findings.append(Finding(manifest.rel, npmrc_rel, "missing", f"{npmrc_rel} {'says nothing about ' + KEY if exists else 'does not exist'}"))
        else:
            findings.append(Finding(manifest.rel, npmrc_rel, "opted-out", f"{npmrc_rel} sets {KEY}={value} explicitly"))
    return findings, unreadable, total


def _probe(root: str) -> int:
    findings, unreadable, total = survey(root)
    if unreadable:
        print("\n".join(unreadable))
        return 3
    if not findings:
        # Positive evidence either way: the tree was walked and either holds no manifest at all,
        # or holds manifests none of which declares a range for npm to enforce.
        print(f"no package.json here declares engines.node ({total} project manifest(s) read), so there "
              f"is no range for npm to enforce and {NPMRC} has nothing to make strict")
        return 1
    opted_out = [f for f in findings if f.state == "opted-out"]
    unreadable_rc = [f for f in findings if f.state == "unreadable"]
    missing = [f for f in findings if f.state == "missing"]
    if opted_out or unreadable_rc:
        print(f"{len(opted_out) + len(unreadable_rc)} of {len(findings)} manifest(s) declaring a range need "
              f"an answer this step will not give itself:")
        for finding in opted_out + unreadable_rc:
            print(f"  {finding.rel}: {finding.detail}")
        print(f"An explicit {KEY}=false is a deliberate opt-out and this step never reverses one. Remove "
              f"that line if it is stale and re-run, or record declined with the reason it is there.")
        return 2
    if not missing:
        # Reached only by a direct run: /adopt runs verify first, and verify passes on exactly this
        # shape. Positive evidence all the same — every declaring manifest was read and each has the
        # flag beside it.
        print(f"already enforced: all {len(findings)} manifest(s) declaring engines.node have an {NPMRC} "
              f"beside them setting {SETTING}")
        return 1
    print(f"{len(missing)} of {len(findings)} manifest(s) declare engines.node while the .npmrc beside them "
          f"does not make it a hard error:")
    for finding in missing:
        print(f"  {finding.rel}: {finding.detail}")
    return 0


def write_setting(root: str, finding: Finding) -> str:
    """Append the flag to the sibling .npmrc, creating it when there is none. "" on success.

    Appending rather than rewriting: an .npmrc carries registry and auth settings this step
    knows nothing about, and the one line it owns is the one it adds.
    """
    path = os.path.join(root, *finding.npmrc.split("/"))
    existing = nm.read_text(root, finding.npmrc)
    if existing is None:
        body = "\n".join([*COMMENT, SETTING]) + "\n"
        return nm.write_atomic(path, body) or ""
    line_end = nm.newline_of(existing)
    lead = "" if not existing or existing.endswith(("\n", "\r")) else line_end
    separator = line_end if existing.strip() else ""
    body = existing + lead + separator + line_end.join([*COMMENT, SETTING]) + line_end
    return nm.write_atomic(path, body) or ""


def _apply(root: str, dry_run: bool) -> int:
    findings, unreadable, total = survey(root)
    if unreadable:
        print("\n".join(unreadable))
        print("Nothing was written.")
        return 3
    blocked = [f for f in findings if f.state in ("opted-out", "unreadable")]
    if blocked:
        print(f"stopped without writing anything — reversing a deliberate {KEY}=false is not this step's "
              f"call, and an {NPMRC} it cannot read is not one it may append to:")
        for finding in blocked:
            print(f"  {finding.rel}: {finding.detail}")
        return 3
    missing = [f for f in findings if f.state == "missing"]
    if not missing:
        if not findings:
            print(f"no package.json here declares engines.node ({total} project manifest(s) read), so there "
                  f"is nothing for {SETTING} to enforce")
            return 3
        print(f"already enforced: all {len(findings)} manifest(s) declaring engines.node have an {NPMRC} "
              f"beside them setting {SETTING}; nothing was written")
        return 0
    if dry_run:
        for finding in missing:
            exists = os.path.isfile(os.path.join(root, *finding.npmrc.split("/")))
            print(f"would {'append to' if exists else 'create '}  {finding.npmrc}  ({len(COMMENT)} comment "
                  f"line(s) and {SETTING}, for {finding.rel})")
        print(f"{len(missing)} .npmrc file(s) would gain {SETTING}")
        return 0
    for finding in missing:
        failure = write_setting(root, finding)
        if failure:
            print(f"{finding.npmrc} {failure} — every .npmrc this step had not reached is untouched")
            return 3
    after, unreadable, _ = survey(root)
    if unreadable:
        print("\n".join(unreadable))
        return 3
    state = {finding.rel: finding for finding in after}
    failed = False
    for finding in missing:
        result = state.get(finding.rel)
        if result is None or result.state != "conformant":
            print(f"NOT SET  {finding.npmrc}: {result.detail if result else 'the manifest is gone'}")
            failed = True
        else:
            print(f"ok       {finding.npmrc} sets {SETTING}, enforcing the range in {finding.rel}")
    if failed:
        return 3
    print(f"{len(missing)} .npmrc file(s) now set {SETTING} beside the manifest whose engines.node they "
          f"enforce ({', '.join(finding.npmrc for finding in missing)}); each asserted back off disk")
    return 0


def _verify(root: str) -> int:
    findings, unreadable, total = survey(root)
    if unreadable:
        print("\n".join(unreadable))
        return 3
    if not findings:
        # Not a pass. "Every manifest declaring a range enforces it" is true of a repo declaring no
        # range anywhere, and an applied line there would claim work in a repo this never reached.
        print(f"no package.json here declares engines.node ({total} project manifest(s) read), so there is "
              f"no enforcement to assert either way")
        return 2
    for finding in findings:
        print(f"{'ok  ' if finding.state == 'conformant' else 'FAIL'}  {finding.rel}: {finding.detail}")
    if any(finding.state != "conformant" for finding in findings):
        return 3
    print(f"all {len(findings)} manifest(s) declaring engines.node have an {NPMRC} beside them setting {SETTING}")
    return 0

# The three entry points, each turning a refusal from the shared walk into the sentence saying what
# was never established. Caught per command because the right code differs, and `probe` is the one
# that matters: a probe exiting 3 ends the whole /adopt walk (SKILL.md §4), which would leave a repo
# git cannot answer about with no route to `n/a` or `declined` for this version or any after it.
# Exit 2 with the question restores the route the walk had before the filter existed. `verify` owes
# 2 as well — the shape went unobserved rather than observed and found wrong — and `apply` owes 3.
# `_dispatch` would also exit 3 but print a traceback, and `audit` records a step against the first
# line of its output.

def cmd_verify(root: str) -> int:
    try:
        return _verify(root)
    except nm.GitRefused as exc:
        print(exc)
        return 2


def cmd_probe(root: str) -> int:
    try:
        return _probe(root)
    except nm.GitRefused as exc:
        print(f"{exc}.")
        print("Resolve what git could not answer and re-run, or record n/a or declined with that reason. "
              "This is a question rather than an error on purpose: a probe exiting 3 would stop the walk "
              "here and leave this repo unable to record this version or any after it.")
        return 2


def cmd_apply(root: str, dry_run: bool) -> int:
    # Asked before anything is written, so the two refusals can be told apart. Without it the catch
    # below cannot know whether the tree was touched, and idempotence rule 2 — every source artifact
    # survives every failure — is a claim `apply` has to be able to make honestly.
    try:
        nm.manifests(root)
    except nm.GitRefused as exc:
        print(f"{exc}. Nothing was written.")
        return 3
    try:
        return _apply(root, dry_run)
    except nm.GitRefused as exc:
        print(f"{exc} — and git answered that same question a moment ago, so this arose mid-run and the "
              f"tree may hold files this command created. Re-run apply once git can answer: it reaches "
              f"the same end state from a half-finished run as from a clean one.")
        return 3


if __name__ == "__main__":
    raise SystemExit(_dispatch.run(__file__, cmd_probe, cmd_apply, cmd_verify))
