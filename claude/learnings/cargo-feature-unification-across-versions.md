# A feature you never declared disappears when a dependency moves to another minor

Declare every Cargo feature your own code calls into, even one the build already compiles
with. Cargo unifies features only across uses of **one semver-compatible version** of a crate.
While your crate and a transitive dependency both resolve `windows` 0.61, the features either
of them names are switched on in the single shared copy, so a method gated on a feature only
the other crate declared compiles for you too. When that dependency moves to an incompatible
version (0.61 → 0.62 is incompatible below 1.0), the graph splits into two copies, each built
with only its own users' features. Your copy loses the borrowed feature and every method it
gated, without any change to your code or your manifest.

## What it looks like

The failure is `E0599 no method named … found`, pointing into the dependency's generated
source, which reads as an API change rather than a missing feature:

```
error[E0599]: no method named `CreatePropertyCondition` found for struct `IUIAutomation`
help: there is a method `CreateNotCondition` with a similar name
```

The method still exists in that version. Read the `#[cfg(...)]` above its definition in
`~/.cargo/registry/src/*/<crate>-<version>/src/...`, and compare it against the features your
`Cargo.toml` lists. The one you lack is the one that was borrowed.

Measured 2026-10-04: a tauri bump moved tao and wry from `windows` 0.61 to 0.62. The app's own
`windows = "0.61"` dependency had never listed `Win32_System_Ole`, which gates
`IUIAutomation::CreatePropertyCondition` and `GetCurrentPropertyValueEx`, and three call sites
stopped compiling. `Cargo.lock` held both `windows` 0.61.3 and 0.62.2 at that point.

## The fix and how to confirm it

Add the feature explicitly. Where the point of pinning the version was to share one copy with
the rest of the graph, raise the pin to the version the dependencies now use as well, then
check that the lock holds one entry per crate name:

```bash
grep -n -A1 '^name = "windows"$' Cargo.lock   # one version listed, not two
```

Raising the version alone is not enough. The feature has to be declared for your copy whether or
not it is shared, because the next split removes it again.

## It hides behind a platform gate

A split like this only breaks the platform the gated code compiles for. When that code is
`cfg(windows)` and the graph cannot cross-compile, a `cargo check` on another OS passes, and the
breakage first shows up in CI or on the other machine. Build the bump on the platform it
affects before calling it done.
