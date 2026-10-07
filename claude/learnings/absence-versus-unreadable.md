# Telling "it is not installed" from "I could not look"

A check for whether something is installed usually gets written as one existence test, and that test
answers the same way for two states a caller must treat differently: the thing is genuinely absent, or
it is there and the probe could not see it. Where the absent branch does something permissive — fall
back, skip a step, pick a default — collapsing them makes the permissive branch fire on a machine that
has the thing, under a message asserting it does not.

Measured on macOS, October 2026, in Node, except where a section names its own platform; the errno
behaviour is the OS's, so the same split applies from Python, Go or a shell.

## `existsSync` answers false for three different states

| state | `existsSync` | `lstatSync` | `statSync` |
|---|---|---|---|
| nothing at that path | false | ENOENT | ENOENT |
| symlink resolving to nothing | false | **succeeds** | ENOENT |
| enclosing directory unreadable (mode 000) | false | EACCES | EACCES |
| target directory unreadable (mode 000) | **true** | succeeds | **succeeds** |

Two of those rows are the trap. A dangling symlink is indistinguishable from absence under
`existsSync`, and so is a path whose parent cannot be traversed.

The last row is the opposite surprise and worth knowing on its own: a directory can be `stat`ed without
being readable, because `stat` needs only to traverse to it. So an unreadable *target* directory passes
every presence test and fails later, when something tries to open what is inside it.

## The three-answer predicate

`lstat` first, then `stat`, and let the pair name the state:

```js
function presence(path) {
  let linked = true
  try { lstatSync(path) } catch (e) {
    if (e.code === "ENOENT") linked = false
    else return { state: "damaged", why: `${path} could not be read (${e.code})` }
  }
  try { statSync(path); return { state: "present" } } catch (e) {
    if (e.code !== "ENOENT") return { state: "damaged", why: `${path} could not be read (${e.code})` }
    if (linked) return { state: "damaged", why: `${path} is a link that resolves to nothing` }
    return { state: "absent" }
  }
}
```

Only `absent` takes the permissive branch. `damaged` stops, and says which of the two it decided it was
in — a non-zero exit is not enough on its own, because the person reading it has to know whether to
repair something or to install something.

## Exercising the absent branch needs the right variable

A probe rooted at `os.homedir()` is not redirected by `HOME` on Windows: `homedir()` reads `USERPROFILE`
there, so a test pointing `HOME` at a scratch directory finds the real install and silently measures the
present branch instead. Verified on Windows 11 with Node v24.19.0 — with `HOME` alone redirected the run
resolved against the genuine tree; with `USERPROFILE` redirected it took the absent branch as intended.
Redirecting `USERPROFILE` also moves rustup and cargo out of reach, so keep `RUSTUP_HOME` and
`CARGO_HOME` pointed at the real ones or the failure arrives from a toolchain lookup rather than from the
code under test.

Note which branch an empty directory takes. It passes `stat`, so the predicate answers `present` and the
failure surfaces when the library is loaded rather than when the path is probed — the right outcome, since
both are damage, but the message a reader gets is the loader's, not the predicate's.

## Why the distinction is worth the extra call

A symlinked install is the common shape that breaks the single test. A dotfiles tree is typically
symlinked into a git checkout, so moving or renaming that checkout — which a `/move-project` skill
exists to do — leaves the link dangling. A fallback gated on `existsSync` then fires on the
owner's own machine, binds a resource nothing allocated, and prints that no registry is installed, while
the registry's own record still points at the resource nobody is using. The permissive branch was written
for a machine that never had the thing, and it ran on the machine that did.

The same reasoning decides what counts as damage rather than absence further in. A library that is
present and *fails* — a syntax error, a pruned subdirectory, a refusal from the tool it wraps — is
damage too, so a `try`/`catch` around the load belongs on the damaged side of the same split rather than
quietly falling through to the default.
