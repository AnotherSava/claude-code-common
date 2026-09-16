"""A declared Node range is enforced by npm rather than merely advertised.

npm reads `engines` and then installs anyway: the range is advisory, so it prints a warning into a
wall of install output and carries on. A project can therefore have its `engines.node`, its
`.nvmrc` and its base image all agreeing while somebody quietly builds on another runtime, and the
failure surfaces far from its cause — one such install of a Node-22 project under Node 24 presented
as 245 unrelated-looking TypeScript errors, not as a version complaint. Setting `engine-strict=true`
in the `.npmrc` beside the manifest turns that into `EBADENGINE`, which stops the install.

Only a manifest that declares `engines.node` is in scope, because a project declaring no range has
nothing for npm to enforce. The node-engines rule is what asserts the range is there at all.

The file read here is the `.npmrc` **beside** package.json and never one higher up the tree. npm
resolves the project config from the directory that holds the manifest, so a file at a repo root is
not read at all when npm runs in `web/` — which is why `_node.sibling` is what builds the path.

An `.npmrc` that is there and will not read raises out of `_node.read_text`, so the runner reports
this rule unmeasured. Absence is the other case entirely and is an answer: no file beside the
manifest means nothing enforces the range, which is a finding.
"""

import re

import _node

NPMRC = ".npmrc"
KEY = "engine-strict"
SETTING = f"{KEY}=true"
# An .npmrc line is `key = value` in ini form. A line whose first non-space character opens a
# comment is skipped; everything else has to hold an `=` or this rule does not know what it is.
ASSIGNMENT_RE = re.compile(r"^\s*([A-Za-z0-9_.@/-]+)\s*=\s*(.*?)\s*$")


def strict_value(text: str | None) -> str | None:
    """The last value an .npmrc assigns to engine-strict, or None when it assigns none.

    The last assignment is the effective one, as it is for every ini file npm reads, so a file that
    sets the key twice is answered the way npm would answer it rather than by whichever line this
    reader saw first.
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


def declares_range(manifest: _node.Manifest) -> bool:
    """Whether this manifest declares an engines.node range for npm to enforce."""
    engines = manifest.data.get("engines")
    node = engines.get("node") if isinstance(engines, dict) else None
    return isinstance(node, str) and bool(node.strip())


def check(root: str) -> list[str]:
    """One line per manifest whose declared range npm would warn about and install past."""
    violations: list[str] = []
    for manifest in _node.read_all(root):
        if not declares_range(manifest):
            continue
        npmrc_rel = _node.sibling(manifest.rel, NPMRC)
        text = _node.read_text(root, npmrc_rel)
        value = strict_value(text)
        if value == "true":
            continue
        if value is None:
            says = f"{npmrc_rel} says nothing about {KEY}" if text is not None else f"there is no {npmrc_rel} beside it"
            violations.append(f"{manifest.rel} declares engines.node and {says}, so npm warns about a wrong runtime and installs on it anyway")
        else:
            violations.append(f"{manifest.rel} declares engines.node while {npmrc_rel} sets {KEY}={value} explicitly, which turns the range back into the advice {SETTING} exists to replace")
    return violations
