# Changing a config file under a running app

An edit to a running app's config file gets undone silently, in two different ways, and both leave the file
on disk reading exactly as it was written. The app may never read it — plenty of apps load config once into
memory at startup — or it writes its own in-memory copy back over yours at the next save, which a window
move, a tray toggle or a graceful quit each trigger. Either way the process keeps the old value while the
file shows the new one, so every check short of the app's own behaviour passes.

## Read the load path before editing anything

Two shapes, wanting opposite procedures:

- **Load-once.** A constructor that reads the file into a mutex at startup, with no watcher, leaves an
  external edit invisible until the next start. Stop the app, edit, start.
- **Watched.** A `notify` / `ReadDirectoryChangesW` watcher on the file or its parent re-reads on
  modification, so an edit takes effect in place.

Grep for the watcher rather than inferring it from a doc comment. One app's comment said the field
"hot-reloads (the pusher re-reads config each cycle)", which is true of the in-memory snapshot and says
nothing about the disk; the watcher lived in a different module and was what actually made the claim true.
Look for a write path too before assuming the file is the only route — an HTTP or IPC route that sets config
does the job without any of this, and a field with no settings UI usually has none.

## A write from WSL does not trip a Windows watcher

Measured 2026-09-26: a Windows app watching `%APPDATA%\<id>\config.json` never fired for that file written
with `tee` from inside WSL, through the same path under `/mnt/c`. The file read back byte-for-byte as
written, the app kept the old value, and the symptom was indistinguishable from an app that ignores its
config. A write crossing the WSL boundary is not a Win32 file operation, so nothing raises the notification
the watcher waits on.

Restarting the app is the reliable fix. Making the watcher fire instead takes a Win32-side write — a
PowerShell read-and-rewrite of the same file — which over SSH is a remote script drop, so expect a
permission gate to stop it.

## Force-kill, then edit, then start

A graceful quit is the wrong verb when an external edit has to survive: the shutdown path persists the
in-memory config over the file. `taskkill /F` and `kill -9` skip that save. The order that works is stop,
edit, start — stopping after the edit is what loses it.

## A deploy is not a restart

Where the installed config is rendered from a template at deploy time, its values come from the secret store
rather than from any file on the box, so a "restart" that reverts the change was a deploy. Timestamps
identify one: the executable and the config rewritten seconds apart. Rotate the value in the store first and
deploy after, since the reverse order reverts what the rotation just did.

## Verify the process, not the file

A config file holding the new value proves nothing about what the process holds in memory, which is the
whole failure above. Assert the behaviour the value controls instead. For a shared secret that means an
authenticated request with the **old** value required to fail and the new one required to succeed, run
against both ends — a rotation that reached one side looks identical from the file system to one that
reached neither.
