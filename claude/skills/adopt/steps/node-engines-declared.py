#!/usr/bin/env python3
"""v7 — every project package.json declares the Node range its .nvmrc already names.

A project that pins Node in one place and not the other builds on whatever runtime the
machine happened to have. The `.nvmrc` tells a developer's shell; `engines.node` tells npm,
CI and every tool that reads a manifest, and v8 is what turns that declaration from advice
into a hard error. This step writes the second from the first, so no version is invented:
the range is derived from the `.nvmrc` sitting beside the manifest, and a manifest with no
`.nvmrc` beside it is a question rather than a guess — "24" and a deliberate older pin read
identically from a file that does not exist.

    node-engines-declared.py probe  <repo-root>              0 applies · 1 no · 2 ask · 3 error
    node-engines-declared.py apply  <repo-root> [--dry-run]  0 done · 3 stopped, nothing written
    node-engines-declared.py verify <repo-root>              0 in shape · 2 unobservable · 3 not

Verify asserts that the two files agree, never that either names a particular major. A
check for "is it 24" would fail the whole fleet the day the LTS line moves and would keep
failing in every `audit` run after it — a permanent false alarm is how a real finding stops
being read.
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

NVMRC = ".nvmrc"
# A .nvmrc holds one version, optionally `v`-prefixed and optionally partial. `lts/jod` and
# `node` are legal there too and name no number at all, which is exactly the case this step
# refuses rather than resolving against a table of release names it would have to keep current.
NVMRC_RE = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?$")
# One comparator of a range: an optional operator, then a version with x-ranges allowed.
# Anything else — a hyphen range, a prerelease tag, a build suffix — does not match, and a
# range this cannot read is reported as unread rather than assumed to agree.
TERM_RE = re.compile(r"^(>=|<=|>|<|=|\^|~)?\s*v?(\d+|[xX*])(?:\.(\d+|[xX*]))?(?:\.(\d+|[xX*]))?$")

Version = tuple[int, int, int]


class Finding(NamedTuple):
    rel: str
    # "conformant" · "derivable" · "blocked" · "unread-range". The last is its own state rather
    # than a shade of "blocked" because verify answers it differently — a range written in a form
    # this step does not parse leaves the shape unobserved (exit 2) while a real disagreement is a
    # shape failure (exit 3) — and telling them apart by matching the wording of a message is the
    # overloaded-field trap: the discriminator has to be the field, not the prose beside it.
    state: str
    detail: str
    nvmrc: str   # the sibling's repo-relative path, for the messages
    target: str  # the range apply would write, set only when state is "derivable"


def parse_nvmrc(text: str | None) -> tuple[Version | None, str]:
    """(the version a .nvmrc names, the text it actually holds). The text is "" when absent.

    A partial `24` is read as 24.0.0 — the lowest runtime that pin permits. That is the
    conservative reading on purpose: a range the lowest permitted version fails is a range
    the pin does not actually guarantee, and reporting that disagreement is the point. The
    literal text travels alongside so a message quotes the file rather than this reading of
    it; printing `24.0.0` for a file that says `24` describes a file nobody wrote.
    """
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = NVMRC_RE.match(stripped)
        if not match:
            return None, stripped
        major, minor, patch = match.groups()
        return (int(major), int(minor or 0), int(patch or 0)), stripped
    return None, ""


def _term_bounds(token: str) -> list[tuple[str, Version]] | None:
    """One comparator as explicit `>=`/`<`/`<=` bounds, or None when it cannot be read."""
    match = TERM_RE.match(token)
    if not match:
        return None
    operator = match.group(1) or ""
    parts = [None if part is None or part in "xX*" else int(part) for part in match.groups()[1:]]
    major, minor, patch = parts
    if major is None:
        return []
    if operator in ("", "=") and (minor is None or patch is None):
        high = (major + 1, 0, 0) if minor is None else (major, minor + 1, 0)
        return [(">=", (major, minor or 0, 0)), ("<", high)]
    if operator == "^":
        low = (major, minor or 0, patch or 0)
        if major > 0:
            high = (major + 1, 0, 0)
        elif minor is None:
            high = (1, 0, 0)
        elif minor > 0:
            high = (0, minor + 1, 0)
        else:
            high = (0, 0, (patch or 0) + 1)
        return [(">=", low), ("<", high)]
    if operator == "~":
        high = (major, minor + 1, 0) if minor is not None else (major + 1, 0, 0)
        return [(">=", (major, minor or 0, patch or 0)), ("<", high)]
    if minor is None or patch is None:
        low = (major, minor or 0, patch or 0)
        if operator in (">=", "<"):
            return [(operator, low)]
        if operator == ">":
            return [(">=", (major + 1, 0, 0) if minor is None else (major, minor + 1, 0))]
        return [("<", (major + 1, 0, 0) if minor is None else (major, minor + 1, 0))]
    exact = (major, minor, patch)
    return [(">=", exact), ("<=", exact)] if operator in ("", "=") else [(operator, exact)]


def satisfies(version: Version, text: str) -> bool | None:
    """Whether `version` falls inside the range, or None when the range cannot be read."""
    for clause in text.split("||"):
        bounds: list[tuple[str, Version]] = []
        tokens = clause.split()
        if not tokens:
            return None
        for token in tokens:
            part = _term_bounds(token)
            if part is None:
                return None
            bounds.extend(part)
        if all((version >= bound if operator == ">=" else
                version > bound if operator == ">" else
                version <= bound if operator == "<=" else
                version < bound) for operator, bound in bounds):
            return True
    return False


def declared(manifest: nm.Manifest) -> str:
    engines = manifest.data.get("engines")
    node = engines.get("node") if isinstance(engines, dict) else None
    return node.strip() if isinstance(node, str) and node.strip() else ""


def survey(root: str) -> tuple[list[Finding], list[str]]:
    """Every project manifest classified, plus the manifests that could not be read at all."""
    findings: list[Finding] = []
    unreadable: list[str] = []
    for manifest in nm.read_all(root):
        if manifest.error:
            unreadable.append(manifest.error)
            continue
        nvmrc_rel = nm.sibling(manifest.rel, NVMRC)
        pinned, shown = parse_nvmrc(nm.read_text(root, nvmrc_rel))
        says = f"{nvmrc_rel} holds {shown!r}, which names no version" if shown else f"there is no {nvmrc_rel} beside it"
        range_text = declared(manifest)
        if not range_text and pinned is not None:
            target = f">={pinned[0]} <{pinned[0] + 1}"
            findings.append(Finding(manifest.rel, "derivable", f"no engines.node; {nvmrc_rel} names {shown}", nvmrc_rel, target))
        elif not range_text:
            findings.append(Finding(manifest.rel, "blocked", f"declares no engines.node and {says}, so which Node it targets is written nowhere in this repo", nvmrc_rel, ""))
        elif pinned is None:
            findings.append(Finding(manifest.rel, "blocked", f"declares engines.node {range_text!r} and {says}, and this step will not invent the version a developer's shell should install", nvmrc_rel, ""))
        else:
            agrees = satisfies(pinned, range_text)
            if agrees is None:
                findings.append(Finding(manifest.rel, "unread-range", f"declares engines.node {range_text!r}, which this step cannot read as a version range, so its agreement with {nvmrc_rel} was never asserted", nvmrc_rel, ""))
            elif not agrees:
                findings.append(Finding(manifest.rel, "blocked", f"declares engines.node {range_text!r} while {nvmrc_rel} names {shown}, which that range excludes", nvmrc_rel, ""))
            else:
                findings.append(Finding(manifest.rel, "conformant", f"engines.node {range_text!r}, and {nvmrc_rel} names {shown}", nvmrc_rel, ""))
    return findings, unreadable


def report(findings: list[Finding], wanted: tuple[str, ...]) -> None:
    for finding in findings:
        if finding.state in wanted:
            print(f"  {finding.rel}: {finding.detail}")


def cmd_probe(root: str) -> int:
    findings, unreadable = survey(root)
    if unreadable:
        print("\n".join(unreadable))
        return 3
    if not findings:
        # CD4's own example of positive evidence: the convention has no subject in this repo,
        # and that was read off a walk of the whole tree rather than off one path's absence.
        print(f"no package.json outside node_modules/ and the other build and dependency trees this "
              f"step never descends into — there is no Node project here to declare a range for")
        return 1
    blocked = [f for f in findings if f.state in ("blocked", "unread-range")]
    derivable = [f for f in findings if f.state == "derivable"]
    if blocked:
        print(f"{len(blocked)} of {len(findings)} project package.json file(s) here need an answer this "
              f"step cannot read off the repo:")
        report(findings, ("blocked", "unread-range"))
        print("Settle each line above — write the file that is missing, or correct the one that is "
              "wrong — then re-run this step; record n/a if this repo deliberately targets no "
              "particular Node.")
        if derivable:
            print("The rest would be derivable, and are left alone until the above is settled:")
            report(findings, ("derivable",))
        return 2
    if derivable:
        print(f"{len(derivable)} of {len(findings)} project package.json file(s) declare no engines.node "
              f"while an .nvmrc beside them names the major:")
        report(findings, ("derivable",))
        return 0
    print(f"already declared: all {len(findings)} project package.json file(s) carry engines.node and "
          f"agree with the .nvmrc beside them")
    return 1


def cmd_apply(root: str, dry_run: bool) -> int:
    findings, unreadable = survey(root)
    if unreadable:
        print("\n".join(unreadable))
        print("Nothing was written.")
        return 3
    blocked = [f for f in findings if f.state in ("blocked", "unread-range")]
    if blocked:
        # apply may never guess: a manifest with no .nvmrc beside it names no major to copy, and
        # a disagreement between the two is a human's call about which of them is wrong.
        print("stopped without writing anything — these need an answer this step cannot read off the repo:")
        report(findings, ("blocked", "unread-range"))
        return 3
    derivable = [f for f in findings if f.state == "derivable"]
    if not derivable:
        if not findings:
            print("there is no project package.json here, so there is nothing to declare a range in")
            return 3
        print(f"already declared: all {len(findings)} project package.json file(s) carry engines.node and "
              f"agree with the .nvmrc beside them; nothing was written")
        return 0
    if dry_run:
        for finding in derivable:
            print(f"would write  {finding.rel}  engines.node = {finding.target}   (from {finding.nvmrc})")
        print(f"{len(derivable)} manifest(s) would gain engines.node, derived from the .nvmrc beside each")
        return 0
    for finding in derivable:
        manifest = nm.read(root, finding.rel)
        if manifest.error:
            print(f"{manifest.error} — stopping; the manifests written before this one are already valid JSON")
            return 3
        # Written over three lines at the file's own indent, so the added key reads like every
        # other object in it rather than as the one line somebody pasted.
        indent, line_end = nm.key_indent(manifest.raw), nm.newline_of(manifest.raw)
        literal = f"{{{line_end}{indent * 2}\"node\": {json.dumps(finding.target)}{line_end}{indent}}}"
        updated = nm.insert_key(manifest.raw, "engines", literal, ("scripts", "dependencies", "devDependencies"))
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
    wanted = {finding.rel: finding.target for finding in derivable}
    state = {finding.rel: finding for finding in after}
    failed = False
    for rel, target in wanted.items():
        result = state.get(rel)
        if result is None or result.state != "conformant" or declared(nm.read(root, rel)) != target:
            print(f"NOT WRITTEN  {rel} -> {target}: {result.detail if result else 'the manifest is gone'}")
            failed = True
        else:
            print(f"ok           {rel} -> engines.node {target}   (from {result.nvmrc})")
    if failed:
        return 3
    print(f"{len(wanted)} package.json gained engines.node derived from the .nvmrc beside it "
          f"({', '.join(f'{rel} {target}' for rel, target in wanted.items())}); each asserted back off disk")
    return 0


def cmd_verify(root: str) -> int:
    findings, unreadable = survey(root)
    if unreadable:
        print("\n".join(unreadable))
        return 3
    if not findings:
        # Not a pass. "Every manifest declares a range" is true of a repo holding no manifest, and
        # recording `applied` on that would claim work in a repo the convention never reaches;
        # probe answers this one with positive evidence and the line is recorded n/a.
        print("no project package.json here, so there is no engines range to assert either way")
        return 2
    for finding in findings:
        mark = "ok  " if finding.state == "conformant" else "FAIL"
        print(f"{mark}  {finding.rel}: {finding.detail}")
    if all(finding.state == "conformant" for finding in findings):
        print(f"all {len(findings)} project package.json file(s) declare engines.node and agree with the "
              f".nvmrc beside them")
        return 0
    if all(finding.state in ("conformant", "unread-range") for finding in findings):
        # The shape itself is what could not be observed: the range is there and is written in a
        # form this step does not read, so neither "agrees" nor "disagrees" was established.
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(_dispatch.run(__file__, cmd_probe, cmd_apply, cmd_verify))
