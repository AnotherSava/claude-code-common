#!/usr/bin/env python3
"""v9 — every project package.json pins the npm version through `packageManager`.

Two machines running different npm versions rewrite the lockfile against each other: the
diff touches no real dependency and only metadata — `"peer": true` markers appearing and
disappearing, `devOptional` flipping to `dev`, optional packages pruned and restored — and
it recurs on every install until the manager is pinned. Corepack reads `packageManager` and
shims the manager to exactly that version, so the pin is what makes two checkouts agree.

    package-manager-pin.py probe  <repo-root>              0 applies · 1 no · 2 ask · 3 error
    package-manager-pin.py apply  <repo-root> [--dry-run]  0 done · 3 stopped, nothing written
    package-manager-pin.py verify <repo-root>              0 in shape · 2 unobservable · 3 not

Where the version comes from: this repo, or nowhere. A pin already here is copied, so a repo
holding one manifest at npm@11.17.0 does not end up with a second at some newer number; the
fleet's own spread of 11.17.0 and 11.18.0 is what that rule protects.

A repo naming no version anywhere is a question, not a default. An earlier draft carried the
current stable as a constant and wrote it — and the constant was a *major* above what every
other repo in the fleet pins and above what this machine runs, so Corepack would have fetched
npm 12 and the first install would have rewritten the lockfile, which is the drift this
convention exists to stop. Nothing here asks the network either: idempotence rule 4, and
`authoring-a-step.md` is explicit that a version `npm view` would answer is a question for
the user rather than a lookup. So probe exits 2 with the command that answers it, and apply
writes nothing.

Verify asserts the pinned *form* and never a particular version, because bumping the pin is
a deliberate act taken like a dependency upgrade, not a per-release chore. A check for
today's number would turn every adopted repo into an `audit` failure the day the next npm
ships.
"""

import json
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

KEY = "packageManager"
PIN_RE = re.compile(r"^npm@\d+\.\d+\.\d+$")
OTHER_MANAGERS = ("yarn", "pnpm", "bun")


class Finding(NamedTuple):
    rel: str
    state: str   # "conformant" · "missing" · "other-manager" · "malformed"
    detail: str
    pin: str     # the valid npm pin this manifest carries, "" when it carries none


def classify(manifest: nm.Manifest) -> Finding:
    value = manifest.data.get(KEY)
    if value is None:
        return Finding(manifest.rel, "missing", f"carries no {KEY}", "")
    if not isinstance(value, str):
        return Finding(manifest.rel, "malformed", f"{KEY} is {value!r}, which is not a version string", "")
    text = value.strip()
    if PIN_RE.match(text):
        return Finding(manifest.rel, "conformant", f"{KEY} {text}", text)
    if text.split("@", 1)[0] in OTHER_MANAGERS:
        return Finding(manifest.rel, "other-manager", f"{KEY} {text}, so this project deliberately uses another manager", "")
    return Finding(manifest.rel, "malformed", f"{KEY} {text!r}, which is not `npm@` plus a three-part version", "")


def survey(root: str) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    unreadable: list[str] = []
    for manifest in nm.read_all(root):
        if manifest.error:
            unreadable.append(manifest.error)
            continue
        findings.append(classify(manifest))
    return findings, unreadable


def source_pins(findings: list[Finding]) -> list[str]:
    """The distinct npm pins this repo already names, ascending. One of them is copyable."""
    return sorted({finding.pin for finding in findings if finding.pin})


class Choice(NamedTuple):
    """What to write, or the question to put instead. An empty `pin` means the second."""

    pin: str
    provenance: str  # a mid-sentence fragment, read only when `pin` is set
    question: str    # the whole text a user answers, read only when `pin` is empty


def chosen(findings: list[Finding]) -> Choice:
    """The pin this repo's own manifests decide on, or the question nothing here answers."""
    pins = source_pins(findings)
    if len(pins) == 1:
        holder = next(finding.rel for finding in findings if finding.pin == pins[0])
        return Choice(pins[0], f"copied from {holder}", "")
    if not pins:
        return Choice("", "", "Nothing in this repo names an npm version, and this step will not choose one. "
                             "`npm view npm version` gives the current stable, and `npm view npm dist-tags` "
                             "says whether that major is a prerelease. Check it against what the other repos "
                             "here already pin before taking it: a pin a major above them makes Corepack "
                             "fetch that npm and rewrite the lockfile on the first install, which is the "
                             "drift this convention exists to stop. Add the chosen value to one manifest and "
                             "re-run — every other manifest in this repo then copies it.")
    return Choice("", "", f"This repo names {len(pins)} different npm versions ({', '.join(pins)}), so which "
                          f"one a new manifest should carry is not this step's guess. Settle on one across "
                          f"this repo and re-run.")


def _probe(root: str) -> int:
    findings, unreadable = survey(root)
    if unreadable:
        print("\n".join(unreadable))
        return 3
    if not findings:
        # CD4's own example of positive evidence: the whole tree was walked and holds no manifest
        # outside the generated trees or the paths git hides, so there is no toolchain here to pin.
        print(f"no package.json outside node_modules/, the other build and dependency trees this step "
              f"never descends into, and the paths git hides — there is no Node project here whose "
              f"manager could drift")
        return 1
    blocked = [f for f in findings if f.state in ("other-manager", "malformed")]
    if blocked:
        print(f"{len(blocked)} of {len(findings)} project package.json file(s) carry a {KEY} this step will "
              f"not overwrite:")
        for finding in blocked:
            print(f"  {finding.rel}: {finding.detail}")
        print(f"A project on yarn or pnpm is a deliberate choice, and a malformed pin is a value somebody "
              f"typed for a reason. Correct it by hand and re-run, or record declined with that reason.")
        return 2
    missing = [f for f in findings if f.state == "missing"]
    if not missing:
        print(f"already pinned: all {len(findings)} project package.json file(s) carry {KEY} in the "
              f"npm@x.y.z form")
        return 1
    choice = chosen(findings)
    print(f"{len(missing)} of {len(findings)} project package.json file(s) carry no {KEY}, so npm's version "
          f"is whatever each machine happens to have:")
    for finding in missing:
        print(f"  {finding.rel}: {finding.detail}")
    if not choice.pin:
        print(choice.question)
        return 2
    print(f"The value would be {choice.pin} — {choice.provenance}.")
    return 0


def _apply(root: str, dry_run: bool) -> int:
    findings, unreadable = survey(root)
    if unreadable:
        print("\n".join(unreadable))
        print("Nothing was written.")
        return 3
    blocked = [f for f in findings if f.state in ("other-manager", "malformed")]
    if blocked:
        print(f"stopped without writing anything — a {KEY} that is already there is not this step's to "
              f"replace:")
        for finding in blocked:
            print(f"  {finding.rel}: {finding.detail}")
        return 3
    missing = [f for f in findings if f.state == "missing"]
    if not missing:
        if not findings:
            print("there is no project package.json here, so there is no manager version to pin")
            return 3
        print(f"already pinned: all {len(findings)} project package.json file(s) carry {KEY}; nothing "
              f"was written")
        return 0
    choice = chosen(findings)
    if not choice.pin:
        print("stopped without writing anything — these manifests carry no packageManager:")
        for finding in missing:
            print(f"  {finding.rel}: {finding.detail}")
        print(choice.question)
        return 3
    pin, provenance = choice.pin, choice.provenance
    if dry_run:
        for finding in missing:
            print(f"would write  {finding.rel}  {KEY} = {pin}")
        print(f"{len(missing)} manifest(s) would gain {KEY} {pin} — {provenance}")
        return 0
    for finding in missing:
        manifest = nm.read(root, finding.rel)
        if manifest.error:
            print(f"{manifest.error} — stopping; the manifests written before this one are already valid JSON")
            return 3
        updated = nm.insert_key(manifest.raw, KEY, json.dumps(pin), ("engines", "scripts", "dependencies", "devDependencies"))
        if updated is None:
            print(f"{finding.rel}: its top-level shape could not be read well enough to add one key without "
                  f"reformatting the file, so it was left exactly as it was")
            return 3
        try:
            json.loads(updated)
        except ValueError as exc:
            print(f"{finding.rel}: the text this step built does not parse ({exc}), so it was never written")
            return 3
        failure = nm.write_atomic(os.path.join(root, *finding.rel.split("/")), updated)
        if failure:
            print(f"{finding.rel} {failure} — it is unchanged on disk")
            return 3
    # Read every manifest back off disk and assert per manifest, never on a count: a tally passes
    # the moment one write lands and another is silently skipped.
    after, unreadable = survey(root)
    if unreadable:
        print("\n".join(unreadable))
        return 3
    state = {finding.rel: finding for finding in after}
    failed = False
    for finding in missing:
        result = state.get(finding.rel)
        if result is None or result.pin != pin:
            print(f"NOT WRITTEN  {finding.rel} -> {pin}: {result.detail if result else 'the manifest is gone'}")
            failed = True
        else:
            print(f"ok           {finding.rel} -> {KEY} {pin}")
    if failed:
        return 3
    print(f"{len(missing)} package.json gained {KEY} {pin}, {provenance} "
          f"({', '.join(finding.rel for finding in missing)}); each asserted back off disk")
    return 0


def _verify(root: str) -> int:
    findings, unreadable = survey(root)
    if unreadable:
        print("\n".join(unreadable))
        return 3
    if not findings:
        # Not a pass. "Every manifest pins the manager" is true of a repo holding no manifest, and
        # recording `applied` there would claim work in a repo the convention never reaches; probe
        # answers this one with positive evidence and the line is recorded n/a.
        print("no project package.json here, so there is no manager version to assert either way")
        return 2
    for finding in findings:
        print(f"{'ok  ' if finding.state == 'conformant' else 'FAIL'}  {finding.rel}: {finding.detail}")
    if any(finding.state != "conformant" for finding in findings):
        return 3
    print(f"all {len(findings)} project package.json file(s) pin npm in the npm@x.y.z form "
          f"({', '.join(source_pins(findings))})")
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
