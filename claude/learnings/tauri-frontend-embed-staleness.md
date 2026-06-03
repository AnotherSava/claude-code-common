# Tauri frontend embed staleness on incremental builds

`tauri build` / `cargo build` embeds the frontend (`frontendDist`, e.g. `../dist`) into the binary at compile time via the `generate_context!` proc macro. On an **incremental local build**, a change to *only* the frontend may not be re-embedded — the binary keeps the previously embedded UI and ships a stale frontend. Clean/CI builds are unaffected (nothing is cached), so this bites local "edit UI → deploy → still see old UI" loops.

## Why

- `tauri-build`'s build script registers only `tauri.conf.json` and `capabilities/` as `cargo:rerun-if-changed` inputs — **not** the `dist` dir. Verify for your version:
  `grep rerun-if-changed src-tauri/target/<profile>/build/<pkg>-*/output`
- `generate_context!` reads and embeds the asset files during macro expansion, but on a **stable** toolchain a proc macro cannot register the files it read as compilation dependencies (`proc_macro::tracked_path` is nightly-only).
- So cargo has no signal that the crate depends on `dist`. If no Rust source (or other tracked input) changed, the crate isn't recompiled, the macro isn't re-expanded, and the old embedded assets persist.

Confirmation that it's embed staleness and not a cache:
- `cargo clean -p <pkg>` "fixes" it (forces a full recompile + re-embed). A webview/HTTP cache wouldn't be cleared by that.
- Vite content-hashes the *asset* filenames, so each build changes the JS/CSS URLs — so this particular staleness isn't WebView2 caching of those assets.

> **But a complementary WebView2 cache problem exists too** — and both can be present at once. `index.html` itself is **not** hash-busted (fixed URL), so WebView2 *does* cache it, and the cached HTML keeps pointing at the previous bundle hash. That's a separate *runtime* failure mode with its own fix (wipe `EBWebView` on fingerprint change, before the Builder). See `tauri-webview2-cache-staleness.md`. If a fresh build's new code still doesn't run after this build-time fix, suspect the runtime cache next.

## Fix: fold a dist fingerprint into a tracked rustc-env

`build.rs` computes a content fingerprint of `dist` and emits it as a `rustc-env`; the crate references it via `env!`, so a frontend change flips the value and forces a recompile (re-running `generate_context!` against fresh `dist`). Use `(path, size)` — **not** mtime — so a no-op `vite build` (identical output, fresh timestamps) doesn't force needless recompiles.

```rust
// build.rs
use std::hash::{Hash, Hasher};
use std::path::Path;

fn main() {
    register_frontend_fingerprint(Path::new("../dist"));
    tauri_build::build()
}

fn register_frontend_fingerprint(dist: &Path) {
    println!("cargo:rerun-if-changed={}", dist.display());
    let mut files: Vec<(String, u64)> = Vec::new();
    let mut stack = vec![dist.to_path_buf()];
    while let Some(dir) = stack.pop() {
        let Ok(entries) = std::fs::read_dir(&dir) else { continue };
        for entry in entries.flatten() {
            let path = entry.path();
            println!("cargo:rerun-if-changed={}", path.display());
            match entry.file_type() {
                Ok(ft) if ft.is_dir() => stack.push(path),
                Ok(_) => {
                    let len = entry.metadata().map(|m| m.len()).unwrap_or(0);
                    files.push((path.to_string_lossy().into_owned(), len));
                }
                _ => {}
            }
        }
    }
    files.sort();
    let mut h = std::collections::hash_map::DefaultHasher::new();
    files.hash(&mut h);
    println!("cargo:rustc-env=FRONTEND_FINGERPRINT={:016x}", h.finish());
}
```

```rust
// lib.rs (or wherever generate_context! lives). The env! reference is what makes
// cargo treat the fingerprint as a compile input — without a reader the rustc-env
// is emitted but unused, so it won't force a recompile.
const _: &str = env!("FRONTEND_FINGERPRINT");
```

`std::collections::hash_map::DefaultHasher::new()` is deterministic (fixed keys, unlike `RandomState`), so the fingerprint is stable across runs/machines.

## Verify

- Two consecutive no-change `cargo build`s → the second is a sub-second no-op (no spurious churn from the fingerprint).
- Append a byte to any file under `dist`, build again → `Compiling <pkg>` (re-embed). Before the fix this was a silent no-op.

`beforeBuildCommand` (vite) runs before `cargo build` in `tauri build`, so `dist` exists when `build.rs` runs. On a clean checkout with no `dist` yet, `read_dir` fails gracefully and `tauri_build::build()` reports the missing-dist error as before — no regression.
