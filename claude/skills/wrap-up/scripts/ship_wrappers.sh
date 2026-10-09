#!/usr/bin/env bash
# Reports which of the two per-machine ship wrappers this repo has, resolved from the repo root so
# the answer cannot depend on the directory /wrap-up was invoked from — a cwd-relative `test -f`
# answers "absent" from any subdirectory and the skipped offer looks identical to a project that
# has no wrapper. DEPLOY_TYPE is the only key read out of config/deploy.env: step 8 needs to know
# whether the deploy raises a window before it asks to run it.
set -u

root=$(git rev-parse --show-toplevel 2>/dev/null) || root=""
[ -n "$root" ] || root=$PWD

for verb in deploy publish; do
  if [ -f "$root/scripts/$verb.sh" ]; then
    echo "$verb: present"
  else
    echo "$verb: absent"
  fi
done

deploy_type=$(sed -n 's/^DEPLOY_TYPE=//p' "$root/config/deploy.env" 2>/dev/null | head -1)
echo "deploy type: ${deploy_type:-unknown}"
