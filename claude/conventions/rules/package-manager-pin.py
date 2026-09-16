"""Every project manifest pins the npm version through `packageManager`.

Two machines running different npm versions rewrite the lockfile against each other: the diff
touches no real dependency and only metadata — `"peer": true` markers appearing and disappearing,
`devOptional` flipping to `dev`, optional packages pruned and restored — and it recurs on every
install until the manager is pinned. Corepack reads `packageManager` and shims the manager to
exactly that version, so the pin is what makes two checkouts agree.

What is asserted is the pinned *form* and never a particular version, because bumping the pin is a
deliberate act taken like a dependency upgrade, not a per-release chore. A check for today's number
would turn every adopted repo into a failing commit gate the day the next npm ships, and the fleet's
own spread of 11.17.0 and 11.18.0 would fail it today.

A manifest pinning yarn, pnpm or bun is reported rather than excused. That is the form the version
introducing this rule asserted, and a repo can no longer record an exception of its own, so whether
a project deliberately on another manager satisfies this convention is a question for a later
version — the pins those managers write carry an integrity hash this rule has never been measured
against, which is the reason not to widen it from the armchair.
"""

import re

import _node

KEY = "packageManager"
PIN_RE = re.compile(r"^npm@\d+\.\d+\.\d+$")
OTHER_MANAGERS = ("yarn", "pnpm", "bun")


def violation(manifest: _node.Manifest) -> str:
    """Why this manifest's pin is not the one the convention asks for, "" when it is."""
    value = manifest.data.get(KEY)
    if value is None:
        return f"{manifest.rel} carries no {KEY}, so npm's version is whatever each machine happens to have"
    if not isinstance(value, str):
        return f"{manifest.rel} sets {KEY} to {value!r}, which is not a version string"
    text = value.strip()
    if PIN_RE.match(text):
        return ""
    if text.split("@", 1)[0] in OTHER_MANAGERS:
        return f"{manifest.rel} sets {KEY} {text}, pinning a manager other than npm, and the form this rule asserts is npm@x.y.z"
    return f"{manifest.rel} sets {KEY} {text!r}, which is not `npm@` plus a three-part version"


def check(root: str) -> list[str]:
    """One line per manifest that does not pin npm in the npm@x.y.z form."""
    return [line for line in (violation(manifest) for manifest in _node.read_all(root)) if line]
