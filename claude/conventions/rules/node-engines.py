"""Every project manifest declares the Node range the .nvmrc beside it already names.

A project that pins Node in one place and not the other builds on whatever runtime the machine
happened to have. The `.nvmrc` tells a developer's shell; `engines.node` tells npm, CI and every
other tool that reads a manifest, and the engine-strict rule is what turns that declaration from
advice into a hard error.

What is asserted is that the two files agree, never that either names a particular major. A check
for "is it 24" would fail the whole fleet the day the LTS line moves, and a permanent false alarm
is how a real finding stops being read.

A range written in a form this cannot parse is not a disagreement — it is an unasserted one, so the
rule raises and the runner reports it unmeasured. Returning an empty list there would report a
manifest as agreeing on the strength of never having read it.

Which manifests count is `_node`'s question, not this one's: a package.json inside a build tree or
inside a path git hides is not a manifest anybody maintains.
"""

from __future__ import annotations

import re

import _node

NVMRC = ".nvmrc"
# A .nvmrc holds one version, optionally `v`-prefixed and optionally partial. Both `lts/jod` and
# `node` are legal there too and name no number at all, which is exactly the case this refuses
# rather than resolving against a table of release names it would have to keep current.
NVMRC_RE = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?$")
# One comparator of a range: an optional operator, then a version with x-ranges allowed. Anything
# else — a hyphen range, a prerelease tag, a build suffix — does not match, and a range this cannot
# read is reported as unread rather than assumed to agree.
TERM_RE = re.compile(r"^(>=|<=|>|<|=|\^|~)?\s*v?(\d+|[xX*])(?:\.(\d+|[xX*]))?(?:\.(\d+|[xX*]))?$")

Version = tuple[int, int, int]


def parse_nvmrc(text: str | None) -> tuple[Version | None, str]:
    """(the version a .nvmrc names, the text it actually holds). The text is "" when absent.

    A partial `24` is read as 24.0.0 — the lowest runtime that pin permits. That is the
    conservative reading on purpose: a range the lowest permitted version fails is a range the pin
    does not actually guarantee, and reporting that disagreement is the point. The literal text
    travels alongside so a message quotes the file rather than this reading of it; printing
    `24.0.0` for a file that says `24` describes a file nobody wrote.
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


def declared(manifest: _node.Manifest) -> str:
    """The range a manifest declares, "" when it declares none."""
    engines = manifest.data.get("engines")
    node = engines.get("node") if isinstance(engines, dict) else None
    return node.strip() if isinstance(node, str) and node.strip() else ""


def check(root: str) -> list[str]:
    """One line per manifest whose declared range and sibling .nvmrc do not agree."""
    violations: list[str] = []
    unread: list[str] = []
    for manifest in _node.read_all(root):
        nvmrc_rel = _node.sibling(manifest.rel, NVMRC)
        pinned, shown = parse_nvmrc(_node.read_text(root, nvmrc_rel))
        says = f"{nvmrc_rel} holds {shown!r}, which names no version" if shown else f"there is no {nvmrc_rel} beside it"
        range_text = declared(manifest)
        if not range_text and pinned is not None:
            violations.append(f"{manifest.rel} declares no engines.node while {nvmrc_rel} names {shown}, so npm and CI are told nothing about the range a developer's shell already installs")
        elif not range_text:
            violations.append(f"{manifest.rel} declares no engines.node and {says}, so which Node it targets is written nowhere in this repo")
        elif pinned is None:
            violations.append(f"{manifest.rel} declares engines.node {range_text!r} and {says}, so a developer's shell is told nothing about which Node to install")
        else:
            agrees = satisfies(pinned, range_text)
            if agrees is None:
                unread.append(f"{manifest.rel} declares engines.node {range_text!r}, which this rule cannot read as a version range, so its agreement with {nvmrc_rel} was never asserted.")
            elif not agrees:
                violations.append(f"{manifest.rel} declares engines.node {range_text!r} while {nvmrc_rel} names {shown}, which that range excludes")
    if unread:
        # A range in a form this cannot parse leaves agreement unasserted rather than disproved, so
        # the rule refuses instead of returning what it did establish. Whatever it *did* establish
        # travels in the message: a violation dropped here would sit unseen until somebody fixed an
        # unrelated manifest, which is a worse silence than the one the refusal reports.
        alongside = f" Found alongside and unreported until that is settled: {'; '.join(violations)}." if violations else ""
        raise _node.Unreadable(" ".join(unread) + alongside)
    return violations
