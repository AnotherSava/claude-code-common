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
#   The all-rights-reserved kind could never have come from `--license` in any case:
#   GitHub's license catalogue only carries open-source licenses, so a reservation
#   has to be supplied as text. It lives in this file rather than in a template file
#   so that there is one copy of it and no missing-asset failure mode.
#
# Usage: seed-license.sh <owner/repo> <copyright-holder> <year> [mit|all-rights-reserved]
# The kind defaults to mit.
# Prints the created commit SHA on success.
#
# Note: commits created through the Contents API are not GPG-signed, so this root
# commit shows as unverified. Only the LICENSE commit is affected.

set -euo pipefail

if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
  echo "usage: seed-license.sh <owner/repo> <copyright-holder> <year> [mit|all-rights-reserved]" >&2
  exit 2
fi

SLUG="$1"
HOLDER="$2"
YEAR="$3"
KIND="${4:-mit}"

# Same placeholder spelling as GitHub's own templates, so one substitution serves both kinds.
ALL_RIGHTS_RESERVED='Copyright (c) [year] [fullname]

All rights reserved.

No permission is granted to use, copy, modify, merge, publish, distribute,
sublicense, or sell this software or any part of it. If you have been given
access to this repository, that access does not by itself grant any of those
rights; any permission must be given separately and in writing.'

case "$KIND" in
  mit)
    # No leading slash on the endpoint: Git Bash on Windows rewrites "/licenses/mit"
    # into a filesystem path like "C:/Program Files/Git/licenses/mit".
    TEMPLATE="$(gh api licenses/mit --jq '.body')"
    ;;
  all-rights-reserved)
    TEMPLATE="$ALL_RIGHTS_RESERVED"
    ;;
  *)
    echo "error: unknown license kind '$KIND' (expected mit or all-rights-reserved)" >&2
    exit 2
    ;;
esac

# Check the TEMPLATE, not the substituted text. A template missing one of the two slots
# yields output with nothing left over to find, so checking afterwards sees a clean license
# that in fact names no holder or no year — wrong in a way that is hard to undo once it is
# the root commit. Checking before substitution catches both a missing slot and a template
# whose shape has changed upstream.
for SLOT in '[year]' '[fullname]'; do
  case "$TEMPLATE" in
    *"$SLOT"*) ;;
    *)
      echo "error: $KIND template has no $SLOT placeholder; refusing to commit an unfilled license" >&2
      exit 1
      ;;
  esac
done

TEXT="${TEMPLATE//\[year\]/$YEAR}"
TEXT="${TEXT//\[fullname\]/$HOLDER}"

# openssl is present on both macOS and Git Bash; `base64 -w0` is GNU-only.
CONTENT="$(printf '%s\n' "$TEXT" | openssl base64 -A)"

gh api -X PUT "repos/$SLUG/contents/LICENSE" \
  -f message="Initial commit" \
  -f content="$CONTENT" \
  --jq '.commit.sha'
