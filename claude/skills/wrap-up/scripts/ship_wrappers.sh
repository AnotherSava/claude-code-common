#!/usr/bin/env bash
# Reports which of the two per-machine ship wrappers this repo has, resolved from the project root so the answer
# cannot depend on the directory /wrap-up was invoked from — a cwd-relative `test -f` answers "absent" from any
# subdirectory, and the skipped offer then looks identical to a project that has no wrapper. DEPLOY_TYPE is the
# only key read out of config/deploy.env: step 8 needs to know whether the deploy raises a window before asking
# to run it.
#
# Four anchors rather than one, unlike the deploy and publish targets that share this resolver: they each read a
# single config file and must resolve against that one, while this script reports on a project that may have
# either verb wired and not the other. A publish-only project has no config/deploy.env to anchor on.
set -u

source "$(dirname "${BASH_SOURCE[0]}")/../../shared/repo-root.sh"
root=$(resolve_repo_dir config/deploy.env config/publish.env scripts/deploy.sh scripts/publish.sh)

for verb in deploy publish; do
  if [ -f "$root/scripts/$verb.sh" ]; then
    echo "$verb: present"
  else
    echo "$verb: absent"
  fi
done

deploy_type=$(sed -n 's/^DEPLOY_TYPE=//p' "$root/config/deploy.env" 2>/dev/null | head -1)
echo "deploy type: ${deploy_type:-unknown}"
