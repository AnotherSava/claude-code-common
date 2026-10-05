---
title: A tray icon's left click reaches the app rather than the menu
rules: tray-icon-macos-click
optional: forks
---

## What changed

A tray icon exists so that one click reaches the app behind it. On macOS 27 that click stops
arriving: a status item holding a permanently attached menu loses its left press to the OS, which
presents the menu itself, and the app never hears about it. Every switch the app has for this is
already set — the dashboard's `tray.rs` calls `show_menu_on_left_click(false)`, which the crate
honours in its own code — so the icon that is meant to show and hide a window shows a menu, with
nothing in the repo's own source to explain why. The diagnosis on 2026-10-04 read the handler, the
crate's macOS backend and the Tauri passthrough before it reached the dependency.

So the convention: a repo whose `Cargo.lock` holds `tray-icon` locks **0.25.1 or newer**, where
tauri-apps/tray-icon#365 attaches the menu to the status item only while it is being presented. The
release that first admits that floor through tauri's own requirement is tauri 2.12.1.
The changelog and registry queries both numbers were read from, and why a merge date settles
neither, are in `learnings/cargo-which-release-carries-a-fix.md`.

The floor names `tray-icon` rather than `tauri`, which is the crate a project declares. tauri 2.11.5
requires `tray-icon = "0.24"` and 2.12.1 requires `"0.25"`, so a tauri-keyed floor would say the
right thing only until that requirement moves again — and a version folder is immutable, because
repos run one number at different times and must get the same behaviour from it. The narrower
subject also scopes itself: tauri's tray-icon dependency is optional, so a Tauri app built without a
tray locks no copy at all.

A later floor, when some further defect is fixed upstream, is a later version rather than an edit
here. Bumping a dependency past this floor needs none: that is an ordinary dependency bump in the
repo whose binary it is.

## Migrating an existing repo

There is work here where a `Cargo.lock` that git does not hide holds a `tray-icon` package below
0.25.1. Read the version out of the lock rather than the manifest, which under a range like
`tauri = "2"` names no tray-icon version at all:

```
grep -A1 '^name = "tray-icon"$' src-tauri/Cargo.lock
```

Bring the branch up to date before running anything below. Cargo rewrites the whole lock, the other
machine may have moved it already, and two independently regenerated locks conflict across hundreds
of lines rather than at the one dependency that changed
(`learnings/git-stash-pull-safety.md`).

Then, in the directory holding the manifest, `cargo update`. Under `tauri = "2"` that moves tauri to
2.12.1 and `tray-icon` to 0.25.1 with it; the same command inside a declared range needs no manifest
edit. Two states need one first:

- **The manifest pins tauri below 2.12.1** — `tauri = "2.11"`, or a `--precise` pin recorded in a
  comment. Raise that pin to `"2"` or to at least `2.12.1`, and say in the commit what the old pin
  was holding, because a pin written deliberately is a constraint this version knows nothing about.
- **The repo vendors its dependencies** or carries a `[patch.crates-io]` entry redirecting
  `tray-icon`. The resolved copy is then not the registry's, so `cargo update` moves nothing. Read
  what the patch points at and raise that instead.

What the rewrite costs: every other dependency moves within its declared range in the same pass, so
the previous resolved graph survives only in the commit the lock is replaced in. Review the diff
before committing it — `git diff -- '*/Cargo.lock'` — and treat anything in it beyond the expected
bumps as the other machine's work rather than this one's.

Afterwards:

- Run the repo's own commit gate, not a bare `cargo build`. A dependency bump is exactly the change
  a type error rides in on, and v9 put the real gate in `.claude/commit-checks.sh` for this reason.
- Left-click the tray icon on a Mac and confirm the window shows and hides. Nothing in the repo can
  assert this and the rule above cannot either — it reads a version, which is the proxy, and the
  click is the thing. Where no Mac is to hand, say the floor is in and the click unobserved rather
  than reporting the migration verified.

## When it does not apply

- **No `Cargo.lock` that git does not hide.** The one file a Rust build records its resolved graph
  in was looked for and is not there, and nothing here creates one. A lock under `target/`, or
  inside a scratch clone in a gitignored `tmp/`, is a build's rather than a project's.
- **A lock holding no `tray-icon` package.** tauri's tray-icon dependency sits behind an optional
  feature (`tray-icon = ["dep:tray-icon"]`), so a build that never enables it links no copy, has no
  attached menu, and cannot reach the defect. Positive evidence read off the lock, rather than an
  absence inferred from the source.
- **Every locked copy is already at or above 0.25.1.** A first record then costs nothing in a repo
  that updated before this version existed.

Which platform a repo targets is not one of these, and the floor is asserted on every checkout. One
lock serves every target, whether a binary built from it ever runs on macOS is not readable from the
repo, and the bump costs a project that never ships there nothing.

## Continuing rule

`tray-icon-macos-click` — every `Cargo.lock` a person maintains, with each `tray-icon` package in it
at 0.25.1 or newer, a prerelease of that version counting as below it. It asserts one floor and
never the newest release: keyed on whatever upstream published this morning it would fail every
adopted repo by lunchtime, and the number it does hold marks where one defect was fixed, so it never
moves. Which locks count is git's answer rather than a name list, and a lock that will not open, a
`[[package]]` block with no name or version, and a version string that is not semver each leave the
rule unmeasured rather than passing.
