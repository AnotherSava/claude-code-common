# Tauri 2's glib Dependabot alert cannot be fixed by a lockfile update

Dismiss or leave the glib alert (patched in glib 0.20.0) on a Tauri 2 app, and do not spend time on `cargo update`:
the gtk-rs stack under Tauri 2 requires gtk ^0.18, which pins glib to 0.18.x.

The chain is tauri → tao and tray-icon/muda → gtk 0.18 → glib 0.18. Check whether it still holds by reading the
gtk requirement of the newest tao on crates.io:

```bash
curl -s -A "dep-check" https://crates.io/api/v1/crates/tao/{{tao-version}}/dependencies
```

Checked 2026-11-22: tao 0.37.3 still asks for gtk ^0.18, and the only newer Tauri is a 3.0 alpha. On Windows and
macOS the gtk crates are Linux-only dependencies, so the alert describes code the shipped binary does not contain.
