# Replacing a Homebrew cask app with a build from source

Two copies of one bundle identifier cannot coexist, so putting a locally built app where a cask app
was installed is a replacement rather than an install-alongside — and Homebrew keeps no copy of the
version being removed, so the way back has to be made by hand first. Measured 2026-10-04.

## One bundle identifier means one installed copy

A second bundle carrying the same `CFBundleIdentifier` does not sit beside the first. Both resolve
the same `~/Library/Application Support/<name>` state directory, the same
`~/Library/Preferences/<id>.plist`, and any lock or socket derived from that state path; Launch
Services is then free to open either for `open -b <id>`, a Spotlight hit or a Dock click. An app
whose state directory holds a lock will have one instance refuse to bind while the other owns it.

So install to the path the cask used, and uninstall the cask before copying anything there. A build
whose own default install directory differs — `make deploy` writing to `~/Applications` — needs that
overridden (`make deploy INSTALL_DIR=/Applications`), or both copies exist at once.

## Homebrew keeps no copy of what it is removing

Check before relying on a reinstall as the rollback:

```bash
find ~/Library/Caches/Homebrew -iname '*<name>*'     # empty
ls -l /opt/homebrew/Caskroom/<name>/<version>/       # a symlink to /Applications, not a payload
```

The tap pins one current version, so `brew install --cask <name>` after the fact installs *that*
version, not the one that was running. Take the copy yourself first, with `ditto`, which preserves
the signature:

```bash
ditto /Applications/<name>.app "$HOME/<name>-<version>.app"
codesign --verify --deep --strict "$HOME/<name>-<version>.app"   # exits 0 on the copy
```

That makes the rollback local and offline.

## Uninstall with `--cask`, never with `--zap`

```bash
brew uninstall --cask <name>
```

removes the bundle and the cask's `binary` artifact — typically a symlink under `/opt/homebrew/bin`,
which is what otherwise keeps shadowing the new build's own CLI on `PATH`.

`--zap` additionally deletes `~/Library/Application Support/<name>`,
`~/Library/Preferences/<id>.plist` and the saved-state directory: every workspace, window and
settings file the app ever wrote.

## Reinstalling over a local build is refused, not merged

Homebrew's app artifact will not move onto a target it does not own —
`/opt/homebrew/Library/Homebrew/cask/artifact/moved.rb` raises "It seems there is already an
application at '<target>'" — and the `--adopt` path refuses too, with "It seems the existing
application is different from the one being installed." So any rollback through brew is two steps:

```bash
rm -rf /Applications/<name>.app && brew install --cask <name>
```

## Copy inside the downtime window; do not rebuild there

A deploy target that depends on a build target re-runs the whole build before it copies. Running it
after the cask is gone means a toolchain failure leaves no installed app at all. Build first, then
reduce the window to the two commands the deploy recipe itself runs:

```bash
rm -rf /Applications/<name>.app
cp -R <build-output>/<name>.app /Applications/<name>.app
```

## Verify identity, not liveness

A launched app proves nothing about which bundle launched. Assert a marker the build stamps:

```bash
plutil -extract GitCommit raw /Applications/<name>.app/Contents/Info.plist
plutil -extract CFBundleShortVersionString raw /Applications/<name>.app/Contents/Info.plist
codesign -dv --verbose=2 /Applications/<name>.app 2>&1 | grep -E 'Identifier=|Signature|Authority=|TeamIdentifier'
```

A commit hash baked at build time is the decisive one, because no reinstalled release could report
it. The signature block distinguishes the two just as well: the notarized cask build printed three
`Authority=` lines and `TeamIdentifier=<team>`, the local build `Signature=adhoc` and
`TeamIdentifier=not set`, with `Identifier=` unchanged between them.

A locally built bundle was never downloaded, so it carries no quarantine attribute and Gatekeeper
does not prompt — which also means a passing launch says nothing about whether the bundle would be
accepted anywhere else.

## Where state and permissions go next

Settings migrations run one way. An app that rewrites its settings file on first launch — resolving a
legacy key into a new one — leaves the old file unreadable by the version that was replaced, so a
copy of the state directory taken before the swap is the only route back to it. Take it with `rsync`
rather than `cp -R`: a state directory holding a live unix socket makes `cp -R` print
`is a socket (not copied)`, and `rsync -a --exclude '<name>.sock'` both skips it and gives an exit
status that means something.

Privacy grants are a separate matter with its own surprises — see
`macos-tcc-after-resigning-an-app.md`. For the publishing side of an ad-hoc-signed app, see
`homebrew-cask-unsigned-macos-app.md`.
