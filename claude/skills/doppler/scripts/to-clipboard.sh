#!/bin/bash
# Put a value on the clipboard without ever printing it.
#
# Reports a label, a length and a short digest instead, so the session transcript records WHICH value was copied
# and never the value itself. The digest is also what lets a later check confirm the clipboard still holds it —
# comparing digests proves identity without either side showing the secret.
#
# Called by a repo's generated `scripts/cb.sh` (see the doppler skill), and usable directly:
#   bash to-clipboard.sh "Jellyfin Local key" "$value"
#   printf '%s' "$value" | bash to-clipboard.sh "Jellyfin Local key"
set -euo pipefail

label="${1:?usage: to-clipboard.sh <label> [value]   (value may be piped instead)}"
value="${2-}"
# Piped input is read only when no argument was given, so a value that happens to be empty fails loudly here
# rather than silently clearing the clipboard.
[ -n "${2+set}" ] || value="$(cat)"
[ -n "$value" ] || { echo "to-clipboard: refusing to copy an empty value ($label)" >&2; exit 1; }

case "$(uname -s)" in
  Darwin) printf '%s' "$value" | pbcopy ;;
  # Git Bash exposes the Windows clipboard as a device; writing bytes to it avoids clip.exe, which transliterates
  # non-ASCII through the console codepage.
  *) printf '%s' "$value" > /dev/clipboard ;;
esac

digest() {
  if command -v sha256sum >/dev/null 2>&1; then printf '%s' "$1" | sha256sum | cut -c1-12
  else printf '%s' "$1" | shasum -a 256 | cut -c1-12  # macOS has no sha256sum
  fi
}

printf 'copied: %s (%d chars, sha256 %s)\n' "$label" "${#value}" "$(digest "$value")"
