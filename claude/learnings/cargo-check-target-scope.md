# What a bare `cargo check` compiles, and what a wrapper hides

Two ways a Rust gate can report success over code it never looked at. Both were hit
while adding a warnings-as-errors gate (`RUSTFLAGS="-D warnings"`) to a Tauri
project.

## `--lib --tests` does not compile the bin's plain build

The obvious scope for a warnings gate is `cargo check --lib --tests`. It misses one
thing, and it is not the one people guess.

`cargo metadata` lists three targets for a typical Tauri crate: the lib, the
`src/main.rs` bin, and `build.rs` as a custom-build target. Probed with an unused
function appended to each:

| probe                                        | `--lib --tests` | `--all-targets` |
|----------------------------------------------|-----------------|-----------------|
| bare unused fn in `build.rs`                  | caught (101)    | caught (101)    |
| bare unused fn in `main.rs`                   | caught (101)    | caught (101)    |
| fn live only under `cfg(test)`, in `main.rs`  | **MISSED (0)**  | caught (101)    |

The build script is always compiled — it has to be built before anything else in the
package, so no flag reaches the lib while skipping it. The bin is compiled by
`--tests` **as its own test target**, so a plainly dead item there is caught either
way, and so is one that is literally `#[cfg(test)]`-gated: in that build `cfg(test)`
is on, the item is present, and it is unused. The single escape is an item in the
bin that only *test code* uses — live under `cfg(test)`, dead without it — because
the bin's **plain** build is the one thing `--lib --tests` never performs.

That first row holds only while cargo is building for the host. Passing `--target`,
or setting `build.target` in `.cargo/config.toml`, makes RUSTFLAGS host-exempt —
build scripts and proc macros stop receiving it, so the same unused function in
`build.rs` degrades to a warning and cargo exits 0. Measured: `--all-targets` alone
exits 101, `--all-targets --target x86_64-pc-windows-msvc` exits 0, same crate. The
lib, bin and test rows are unaffected. The config-file trigger is the one to watch,
because it needs no change to the command you run — see the cargo book's
`build.rustflags` entry.

So `--all-targets` closes one hole rather than three. Use it anyway — it is the
same cost and it stops the question being re-derived:

```bash
RUSTFLAGS="-D warnings" cargo check --manifest-path src-tauri/Cargo.toml --all-targets
```

Note the flag is part of cargo's fingerprint, so the first `RUSTFLAGS` run
recompiles the dependency graph and later ones are cached beside the unflagged
artifacts. Dependencies are compiled with `--cap-lints allow`, so a warning in a
crate you do not own cannot fail this.

## `cargo tauri build` injects features that bare `cargo` does not

Tauri cross-checks `tauri.conf.json` against the `tauri` dependency's features and
refuses a config asking for a capability the crate was not built with:

```
The `tauri` dependency features on the `Cargo.toml` file does not match the
allowlist defined under `tauri.conf.json`.
Please run `tauri dev` or `tauri build` or add the `macos-private-api` feature.
```

Setting `"macOSPrivateApi": true` therefore requires
`tauri = { features = ["macos-private-api", …] }`. The trap is that the Tauri CLI
**injects the feature silently**, so `cargo tauri build` and `cargo tauri dev`
succeed while a bare `cargo check` / `cargo test` exits 101. Two consequences:

- The mismatch is *platform-independent* — it is a build-script assertion about
  config versus features, not about the host — so a macOS-only config key still
  breaks a Windows `cargo test`, and vice versa.
- Config and `Cargo.toml` can drift apart indefinitely on a machine that only ever
  builds through the CLI. Whatever runs a bare cargo command (a commit hook, CI) is
  the first thing to notice, on whichever machine commits next.

There is nothing to add as a guard here: the build script already makes the
assertion. What is worth having is knowing which command can see it.
