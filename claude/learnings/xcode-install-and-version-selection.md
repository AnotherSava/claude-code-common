# Installing Xcode, and choosing which version

Picking an Xcode is constrained from two directions at once. The App Store serves exactly one
version and gates it on the OS, while a project may need an older one — and getting it wrong costs a
multi-gigabyte download or an OS upgrade nobody asked for. Everything below was measured on
2026-10-04.

## The App Store offers one version, gated on the OS

Query it rather than guessing, through Apple's public lookup endpoint:

```bash
curl -s "https://itunes.apple.com/lookup?id=497799835" | python3 -c "
import json,sys
r=json.load(sys.stdin)['results'][0]
print(r['version'], r['minimumOsVersion'], r['fileSizeBytes'])
"
```

That returned Xcode `27.0`, `minimumOsVersion` `26.6`, about 3.08 GB compressed. On macOS 26.5.1 the
store therefore offers an OS update instead of Xcode, and clicking Get accomplishes nothing.

There is no Homebrew route: `brew info --cask xcode` answers "No Cask with this name exists".

## `softwareupdate` answers two different questions

On macOS 26.5.1, `softwareupdate --list` named only Safari and the Command Line Tools for Xcode 26.6
— no OS update at all. `softwareupdate --list-full-installers` on the same machine listed full
installers for 26.5.2, 26.6, 26.6.1, 26.6.2, 26.7, 26.7.1 and macOS 27.0/27.0.1.

A missing delta update is not a missing OS version. Read the second command before concluding the
machine cannot move.

## Per-version requirements come from xcodereleases.com

`curl -s https://xcodereleases.com/data.json` returns every release with `version.number`,
`version.build`, `requires` and `links.download.url`. Measured: every Xcode 26.x requires macOS
26.2, while Xcode 27.0 (build 27A266a) requires 26.6. That is what makes an older Xcode the cheaper
answer on a machine one point release behind — Xcode 26.6 runs on 26.2 onward.

## `xcodes` installs any listed version

```bash
brew install xcodes
xcodes list --data-source xcodeReleases   # no Apple sign-in
xcodes install 26.6                       # prompts for an Apple ID password
```

The `--data-source xcodeReleases` form reads the public feed, so listing needs no credentials.
Installing does, and it prompts interactively — run it in a terminal outside Claude Code so the
password never reaches a transcript. `aria2` on PATH makes the download 3-5x faster and
`--experimental-unxip` speeds the expansion.

## The Command Line Tools are not Xcode, and one of the failures is illegible

`xcode-select -p` returning `/Library/Developer/CommandLineTools` makes `xcodebuild` refuse outright,
naming the cause. The other failure does not: `swift test` on a package using swift-testing dies with

```
error: no such module 'Testing'
```

which reads as a broken project. The CLT ships only `usr/lib/swift/host/plugins/testing` — the macro
plugin — and no `Testing` library; swift-testing comes with Xcode. A package that declares no
swift-testing dependency is relying on the bundled copy, so its tests need Xcode even though nothing
in the package says so.

After installing:

```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
```

then open Xcode once to accept the license.

## `xcrun -f metal` reports a path for a toolchain that is absent

The Metal Toolchain is a separate downloadable component, and the obvious probe lies:
`xcrun -f metal` resolves
`/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/metal` while

```
$ xcrun metal --version
error: cannot execute tool 'metal' due to missing Metal Toolchain; use: xcodebuild -downloadComponent MetalToolchain
```

Probe with `xcrun metal --version` and read its exit text, not with `-f`. The download fetched 838.9
MB with no authentication prompt, after which `metal --version` reported `Apple metal version
32023.921` targeting `air64-apple-darwin27.0.0`.
