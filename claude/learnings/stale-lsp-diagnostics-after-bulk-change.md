# Stale LSP diagnostics after a bulk change

A burst of compiler errors in the editor is the one report you are told never to step past, and after a bulk change it is routinely not a failure at all. rust-analyzer re-indexes in the background, so for a few seconds it answers about a file set that is half old, and it reports that mixture as errors with real-looking line numbers.

Two triggers produce it.

- **Your own edit burst** — a `replace_all` across many struct literals, a rename across a package. The lag is easy to attribute here, because you know which files you just changed. The worked case is in `editing-struct-literal-fields-replace-all.md`.
- **A git operation that rewrites many files at once** — a fast-forward merge, a rebase, a stash pop, a branch switch. This one is the trap: you edited nothing, so "my own edits lag" does not explain it, and the errors read as a break the merge caused.

The git trigger also lies about *where*. Measured 2026-10-01 on a Rust/Tauri repo, immediately after a fast-forward of 12 files: 12 errors in two files the merge never touched — `expected 2 arguments, found 1` at nine call sites, `missing structure fields: - read` at another. A `cargo check --all-targets` passed in 7.4 seconds, and the files the merge did change reported nothing.

**Re-run the project's own gate and read its output, before reporting a break or starting to diagnose one.** The tell is errors in files outside the change: compare the diagnostic paths against `git diff --name-only HEAD@{1} HEAD`, or against your own edit list, and treat anything outside it as unmeasured until the compiler agrees.
