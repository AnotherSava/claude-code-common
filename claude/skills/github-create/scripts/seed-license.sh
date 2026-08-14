#!/usr/bin/env bash
# Create the initial commit on an EMPTY GitHub repo: one file, LICENSE, nothing else.
#
# Why this exists instead of `gh repo create --license mit`:
#   gh only sets the API's `auto_init` flag from `--add-readme`, and GitHub applies
#   `license_template` only during auto-init — so `--license mit` alone can yield a
#   repo with no commit at all. Passing `--add-readme` does produce a commit, but it
#   puts README.md in it, which collides with the README the local project already has.
#   The Contents API is GitHub's documented way to bootstrap an empty repo, and it
#   commits exactly the one path given.
#
# Usage: seed-license.sh <owner/repo> <copyright-holder> <year>
# Prints the created commit SHA on success.
#
# Note: commits created through the Contents API are not GPG-signed, so this root
# commit shows as unverified. Only the LICENSE commit is affected.

set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "usage: seed-license.sh <owner/repo> <copyright-holder> <year>" >&2
  exit 2
fi

SLUG="$1"
HOLDER="$2"
YEAR="$3"

# No leading slash on the endpoint: Git Bash on Windows rewrites "/licenses/mit"
# into a filesystem path like "C:/Program Files/Git/licenses/mit".
BODY="$(gh api licenses/mit --jq '.body')"

TEXT="${BODY//\[year\]/$YEAR}"
TEXT="${TEXT//\[fullname\]/$HOLDER}"

if [ "$TEXT" = "$BODY" ]; then
  echo "error: MIT template placeholders not found; refusing to commit an unfilled license" >&2
  exit 1
fi

# openssl is present on both macOS and Git Bash; `base64 -w0` is GNU-only.
CONTENT="$(printf '%s\n' "$TEXT" | openssl base64 -A)"

gh api -X PUT "repos/$SLUG/contents/LICENSE" \
  -f message="Initial commit" \
  -f content="$CONTENT" \
  --jq '.commit.sha'
