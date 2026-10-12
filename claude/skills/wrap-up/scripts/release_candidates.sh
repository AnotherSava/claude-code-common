#!/usr/bin/env bash
# Reports whether this repo has user-facing work since its last release, for /wrap-up step 8's release offer.
# Runs after /commit's push rather than as a Context line: Context is evaluated when the skill loads, before the
# commits this section of work produces exist, so a count taken there would miss exactly the work being wrapped up.
#
# Tags are fetched first because a release cut on the other machine exists here only once fetched, and a stale tag
# list reports that release's commits as unreleased. A failed fetch prints FETCH-FAILED and the count below it is
# against local tags only.
set -u

git rev-parse --git-dir >/dev/null 2>&1 || { echo "release: not a git repo"; exit 0; }
git fetch --tags --quiet 2>/dev/null || echo "FETCH-FAILED"

tag=$(git describe --tags --abbrev=0 --match 'v*' 2>/dev/null)
if [ -z "$tag" ]; then
  echo "release: no v* tag reachable from HEAD"
  exit 0
fi

# feat and fix only: the two kinds /release files under Features and Fixes in its notes. It also reads chore and
# refactor as a patch bump, but those change nothing a user sees, so they do not prompt an offer.
subjects=$(git log "$tag..HEAD" --format=%s | grep -E '^(feat|fix)(\([^)]*\))?!?: ')
if [ -z "$subjects" ]; then
  echo "release: $tag, 0 feat/fix commits since"
else
  echo "release: $tag, $(printf '%s\n' "$subjects" | wc -l | tr -d ' ') feat/fix commits since"
  printf '%s\n' "$subjects"
fi
