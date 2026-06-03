# Uninstalling a macOS app cleanly

A macOS app leaves footprint in 5+ locations beyond `/Applications`:

- `/Applications/<App Name>.app` (or `~/Applications/...`)
- `~/Library/Application Support/<bundle-id>/`
- `~/Library/WebKit/<bundle-id>/` and sometimes `~/Library/WebKit/<exec-name>/`
- `~/Library/Preferences/<bundle-id>.plist`
- `~/Library/Caches/<bundle-id>/` and `~/Library/Caches/<exec-name>/`
- LaunchAgent at `~/Library/LaunchAgents/<Label>.plist` (label from the autostart config)
- LaunchServices DB entries (Spotlight + Open With menus reference these)

## Find all copies first

Before deleting anything, run:

```sh
mdfind "kMDItemCFBundleIdentifier == '<bundle-id>'"
```

This returns *every* installed copy of the bundle on the system regardless of path. Pattern-greps against `/Applications/` miss bundles in unexpected subdirectories — e.g. a project whose `deploy` script installs to `/Applications/<project>/<App>.app` while a separate DMG drag-install lands at `/Applications/<App>.app`. Both have the same bundle ID but different paths; only the Spotlight metadata query finds both.

## Finding what's loaded

- `launchctl print gui/$UID | grep <pattern>` — currently loaded launch agents
- `sfltool dumpbtm` — modern login-items DB (SMAppService / Background Task
  Management); replaces the old
  `osascript -e 'tell application "System Events" to get the name of every login item'`
  which only sees legacy items
- `ps -axo pid,command | grep <pattern>` — running processes

## Finding LaunchServices entries

```sh
lsregister=/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister
"$lsregister" -dump | grep -E "<App Name>.app|<bundle-id>"
```

## Unregistering stale paths

`lsregister -kill -r -domain local -domain system -domain user` was the old
rebuild-the-DB command — **removed in modern macOS** ("dangerous and no longer
useful"). Use targeted unregister instead:

```sh
"$lsregister" -u "/path/to/StaleApp.app"
```

Iterate over each stale path. The dump can list different stale paths on each
query (some entries only surface when their parents are touched), so re-dump
and re-unregister in a loop until clean:

```sh
"$lsregister" -dump | awk '/^path:.*<App Name>.app/ {
    sub(/^path:[ \t]+/,""); sub(/[ \t]+\(0x[0-9a-f]+\)$/,""); print
}' | sort -u | while IFS= read -r p; do
    "$lsregister" -u "$p"
done
```

## Common pitfall: renamed apps still autostarting

When a Tauri app's `productName` / `identifier` changes, the OLD bundle's
LaunchAgent keeps autostarting the OLD binary on login, which writes to the
OLD `~/Library/Application Support/<old-bundle-id>/` dir. Symptoms:

- Recent mtimes on the OLD app-support dir while the new dir also exists
- `launchctl print gui/$UID` shows the new bundle id, but the old binary is
  still in `ps`

Re-running the project's deploy script typically overwrites the LaunchAgent
to point at the new binary path; only the file leftovers and LaunchServices
entries then need manual cleanup.
