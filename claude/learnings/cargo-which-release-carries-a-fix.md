# Which release carries a fix

Pinning a dependency at a floor asserts that one named defect is fixed in whatever a build links. Two
pieces of evidence look like they settle which release that is, and neither does: the date the
upstream fix merged, and the range the parent crate requires.

## The changelog entry names the release, the merge date does not

A merge timestamp and a publish timestamp can sit minutes apart, so comparing them at day resolution
answers nothing. Measured 2026-10-04 on `tauri-apps/tray-icon`: PR #365 merged at
`2026-09-16T01:40:15Z`, and 0.25.1 was published at `2026-09-16T01:45:07Z` — five minutes later, the
same date. A day-resolution comparison is consistent with either order.

The project's own changelog names the PR under the release that shipped it:

```bash
gh api repos/tauri-apps/tray-icon/contents/CHANGELOG.md --jq '.content' | base64 -d
```

Its `[0.25.1]` section carries "([#365]…) Fix left-click events being swallowed on macOS 27 by
attaching the menu to the status item only while it is being presented", which is the record. Where a
project keeps no changelog, `gh release view <tag>` or the tags the merge commit is reachable from
answer the same question.

Publish instants come from the registry, which also marks a yanked version:

```bash
curl -s https://crates.io/api/v1/crates/tray-icon/versions | python3 -c "
import json, sys
for v in json.load(sys.stdin)['versions'][:5]:
    print(v['num'], v['created_at'], 'yanked' if v['yanked'] else '')
"
```

## Read a parent crate's requirement off the registry

One endpoint gives every dependency a published version declares, so this needs no clone and no
resolution:

```bash
curl -s https://crates.io/api/v1/crates/tauri/2.12.1/dependencies | python3 -c "
import json, sys
for d in json.load(sys.stdin)['dependencies']:
    print(d['crate_id'], d['req'], d['kind'], 'optional' if d['optional'] else 'required')
"
```

Each entry carries the `req` range, the `kind` (normal, dev or build) and whether the dependency is
`optional`. Measured 2026-10-04: tauri 2.11.5 requires `tray-icon ^0.24` and 2.12.1 requires
`^0.25`, optional in both.

An optional dependency is absent from the lock of a build that never enables its feature, so a floor
written on such a crate holds with nothing to say in a project that does not use it.

## A caret range on a 0.x version cannot carry a patch floor

Cargo's caret on a `0.y.z` requirement pins the minor: `^0.25` admits 0.25.0 and every later 0.25.x,
and never 0.26.0. Both directions bear on where a floor goes.

- **Upgrading the parent does not deliver the patch.** A parent requiring `^0.25` is satisfied by
  0.25.0, which precedes a fix released in 0.25.1. A plain `cargo update` resolves to the newest
  version in range and does deliver it, so the floor is met by what the resolver picks rather than by
  the requirement. Assert the locked version, never the parent's range.
- **A floor above the parent's range is unsatisfiable.** Keyed on the newest release instead of the
  one that fixed the defect, a floor can name a version no resolution under that parent can reach —
  `^0.25` cannot reach 0.26.0 however new it is. The release that carries the fix is also the number
  that never has to move.

## Read the version out of the lock

A manifest declares a range. The lock records what a build links, and under a range like
`tauri = "2"` the manifest names no transitive crate at all, so the lock is the only file in a repo
that answers which version is in play:

```bash
grep -A1 '^name = "tray-icon"$' src-tauri/Cargo.lock
```
