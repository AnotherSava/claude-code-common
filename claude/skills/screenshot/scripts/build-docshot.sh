#!/bin/bash
# Build the DocShot capture helper into ~/Applications. Run once per machine.
#
# The bundle — not the source — is what macOS grants Screen Recording to, so its
# path and ad-hoc signature must stay put. Rebuilding resets the grant, which is
# why this refuses to clobber an existing install unless asked.
set -euo pipefail
APP="${DOCSHOT_APP:-$HOME/Applications/DocShot.app}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/docshot.swift"

if [ -d "$APP" ] && [ "${1:-}" != "--force" ]; then
  echo "DocShot already installed at $APP"
  echo "Rebuilding resets its Screen Recording grant. Pass --force if that is what you want."
  exit 0
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
swiftc -O -o "$APP/Contents/MacOS/docshot" "$SRC"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>DocShot</string>
  <key>CFBundleDisplayName</key><string>DocShot</string>
  <key>CFBundleIdentifier</key><string>local.docshot</string>
  <key>CFBundleExecutable</key><string>docshot</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <!-- No Dock icon, no menu bar: it must never steal focus from the window
       it is about to photograph. -->
  <key>LSUIElement</key><true/>
</dict></plist>
PLIST

# An ad-hoc signature gives TCC a stable identity to pin the grant to. Without
# one the grant can be invalidated by anything that touches the binary.
codesign --force --sign - "$APP" >/dev/null 2>&1 || echo "note: ad-hoc codesign failed; the grant may not survive"

echo "installed: $APP"
echo
echo "One-time grant, then it is automated from here:"
echo "  System Settings > Privacy & Security > Screen & System Audio Recording > + > $APP"
echo
echo "Verify with:  open -a \"$APP\" --args --list   (titles come back empty until granted)"
