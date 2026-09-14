# Gating a Rust project on warnings, and the blind spots of the obvious command

A project that commits straight to `main` wants its warnings failed on rather than printed —
a warning nobody must act on is a warning nobody reads, and the next real one hides among them.
The command that does it is less obvious than it looks, and every blind spot below reports success
just as confidently as a clean run — which is why each one here was measured rather than reasoned
out from the flag names.

```yaml
- run: cargo check --manifest-path <crate>/Cargo.toml --all-targets
  env:
    RUSTFLAGS: -D warnings
```

## `cargo test` sees only the test cfg

`cargo test` compiles the crate with `cfg(test)` on, so an item that is dead only in the *plain*
build never reaches it. A suite that has passed for months therefore says nothing about whether
the shipped binary compiles clean. Measured case: nine `dead_code` warnings visible in every
release build, invisible to a green `cargo test --lib`, unread for as long as they existed.

## `--lib --tests` is not all targets

Ask the crate what it has rather than assuming:

```bash
python3 <<'EOF'
import json
import subprocess

meta = subprocess.run(["cargo", "metadata", "--no-deps", "--format-version", "1"], capture_output=True, text=True, check=True).stdout
for t in json.loads(meta)["packages"][0]["targets"]:
    print(t["kind"], t["name"], t["src_path"])
EOF
```

Python runs `cargo` itself rather than reading a pipe, because a heredoc already occupies stdin —
`cargo metadata | python3 <<'EOF'` silently feeds the script to Python and throws the JSON away.

A typical Tauri app answers three — the lib, a `src/main.rs` **bin**, and `build.rs` as a
**custom-build** target. Probed with an unused function appended to each:

| probe                                        | `--lib --tests` | `--all-targets` |
|----------------------------------------------|-----------------|-----------------|
| bare unused fn in `build.rs`                  | caught (101)    | caught (101)    |
| bare unused fn in `main.rs`                   | caught (101)    | caught (101)    |
| fn live only under `cfg(test)`, in `main.rs`  | **MISSED (0)**  | caught (101)    |

Only one of those is a blind spot, and not the one it looks like:

- **`build.rs` is always covered.** A build script has to be compiled before anything else in the
  package can be, so no flag reaches the lib while skipping it.
- **The bin is compiled by `--tests`, but only in its test configuration.** Cargo builds
  `src/main.rs` as the bin's own test target, so an item dead in *both* configurations is caught —
  and so is one that is literally `#[cfg(test)]`-gated, since in that build `cfg(test)` is on, the
  item is present, and it is unused. The single escape is an item in the bin that only *test code*
  uses: live under `cfg(test)`, dead without it, because the bin's **plain** build is the one thing
  `--lib --tests` never performs.

That is the first section's `cfg(test)` trap again, one target over. `--all-targets` covers lib,
bins, tests, benches and examples in one pass at no measurable cost, and settles both readings.

**The first row holds only while cargo builds for the host.** Passing `--target`, or setting
`build.target` in `.cargo/config.toml`, makes `RUSTFLAGS` host-exempt — build scripts and proc
macros stop receiving it, so the same unused function in `build.rs` degrades to a warning and cargo
exits 0. Measured on one crate: `--all-targets` alone exits 101, `--all-targets --target
x86_64-apple-darwin` exits 0 — and so does `--target aarch64-apple-darwin`, the host's *own* triple,
so this is not only a cross-compilation concern; naming any target at all is enough. The lib, bin
and test rows are unaffected. The config-file trigger is the one to watch, because it needs no
change to the command you run — see the cargo book's `build.rustflags` entry.

So `--all-targets` closes one hole rather than three. Use it anyway — same cost, and it stops the
question being re-derived.

**Prove it rather than trusting the flag docs — and probe with the right shape.** A bare unused fn
is dead in every configuration, so `--lib --tests` catches it too and the probe then certifies a
gate that still has the hole. The probe must be live under `cfg(test)` and dead without it:

```bash
cat >> src/main.rs <<'EOF'

fn unused_probe() -> u8 { 7 }

#[cfg(test)]
mod unused_probe_t {
    #[test]
    fn t() { assert_eq!(super::unused_probe(), 7); }
}
EOF
RUSTFLAGS="-D warnings" cargo check --manifest-path Cargo.toml --all-targets; echo "exit=$?"
git checkout -- src/main.rs     # restore exactly; a `sed -i` delete can leave the blank line behind
```

`exit=101` with `error: function 'unused_probe' is never used` is the gate working. Exit 0 means the
plain build of that target is not happening, whatever the flag name suggested. Restore with
`git checkout`, not a `sed` delete — an append adds a blank line too, and deleting only the fn
leaves the tree dirty.

## `-D warnings` cannot be failed by someone else's crate

`RUSTFLAGS` reaches every crate in the graph, which looks like it makes the build hostage to any
dependency's lint. It does not: cargo compiles non-path (registry) dependencies with
`--cap-lints allow`, so their warnings are capped before the flag can promote them. Only the
workspace's own crates can fail this.

The real cost is the fingerprint: `RUSTFLAGS` is part of it, so the first flagged run rebuilds the
whole dependency graph and caches it *beside* the unflagged artifacts. Measured on a Tauri app:
50s cold, 1.5–2.9s warm, and the full project check script went from 7.3s to 10.3s.

## Assert the exit status, never a grep for "warning"

```bash
RUSTFLAGS="-D warnings" cargo check --manifest-path <crate>/Cargo.toml --all-targets
```

is the whole check under `set -euo pipefail`. The tempting alternative — capture the output and
`grep -q '^warning'` — reports a **compile error** as a clean run, because an error is not a
warning and the grep finds nothing. Piping the command through `grep` at all discards its exit
code. This is the same trap as any "not run looks like passed" check.

## Silencing what is unreachable on this platform, without going blind on the other

Cross-platform code has items that are live on one OS and unreachable on another. Deleting them is
wrong and a bare `#[allow(dead_code)]` is too broad — it also silences the platform where the item
is reachable and might genuinely rot. Use the condition its callers already carry:

```rust
#[cfg_attr(not(windows), allow(dead_code))]
pub fn observe_caption(..) { .. }
```

**Marking the root is enough for a whole cluster.** rustc seeds its live-symbol walk from
allow-annotated items, so everything reachable *from* an allowed item stops being reported too.
One attribute on the entry point silenced eight further warnings (its callees and two enums) with
no attribute on any of them.

For an **import** used only by cfg-gated code, gate the `use` with the same cfg rather than
allowing the lint — the import then states the same condition its users do:

```rust
#[cfg(not(target_os = "macos"))]
use std::sync::{Mutex, OnceLock};
```

Same for a `let mut` whose only mutation is behind a `#[cfg]`:
`#[cfg_attr(not(target_os = "windows"), allow(unused_mut))]`.

## Each platform's CI leg is the only thing that can see the other's dead code

The consequence of the above: a matrix build is not redundancy here, it is the check. macOS cannot
see code dead only on Windows and vice versa, so both legs must run the gate. Adding it to CI and
finding it clean on one machine settles nothing about the other — unless the target has no platform
axis at all. That is checkable rather than hopeful: a `build.rs` with no `cfg` of any kind and a
`main.rs` whose only one is the debug/release `windows_subsystem` attribute compile to the same
thing everywhere, so one platform's clean result *is* the other's.

## `cargo tauri build` injects features that bare `cargo` does not

A neighbouring way a wrapper hides what bare cargo sees. Tauri cross-checks `tauri.conf.json`
against the `tauri` dependency's features and refuses a config asking for a capability the crate
was not built with:

```
The `tauri` dependency features on the `Cargo.toml` file does not match the
allowlist defined under `tauri.conf.json`.
Please run `tauri dev` or `tauri build` or add the `macos-private-api` feature.
```

Setting `"macOSPrivateApi": true` therefore requires
`tauri = { features = ["macos-private-api", …] }`. The trap is that the Tauri CLI **injects the
feature silently**, so `cargo tauri build` and `cargo tauri dev` succeed while a bare `cargo check`
/ `cargo test` exits 101. Two consequences:

- The mismatch is *platform-independent* — it is a build-script assertion about config versus
  features, not about the host — so a macOS-only config key still breaks a Windows `cargo test`,
  and vice versa.
- Config and `Cargo.toml` can drift apart indefinitely on a machine that only ever builds through
  the CLI. Whatever runs a bare cargo command (a commit hook, CI) is the first thing to notice, on
  whichever machine commits next.

There is nothing to add as a guard here: the build script already makes the assertion. What is
worth having is knowing which command can see it.
