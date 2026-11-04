#!/usr/bin/env bash
# Reports whether this repo has a deploy and a publish configured, resolved from the project root so the answer
# cannot depend on the directory /wrap-up was invoked from — a cwd-relative `test -f` answers "absent" from any
# subdirectory, and the skipped offer then looks identical to a project that has neither. A deploy is configured
# when config/deploy.env exists (the deploy skill's run.sh reads it), or when a repo below convention 017 still
# keeps a per-machine scripts/deploy.sh; a publish when the per-machine scripts/publish.sh exists. DEPLOY_TYPE is
# the only deploy setting read, through deploy_get as run.sh reads it: the ship and release offer step needs to
# know whether the deploy raises a window before asking to run it.
#
# Four anchors rather than one, unlike the deploy and publish targets that share this resolver: they each read a
# single config file and must resolve against that one, while this script reports on a project that may have
# either verb wired and not the other. A publish-only project has no config/deploy.env to anchor on.
set -u

source "$(dirname "${BASH_SOURCE[0]}")/../../shared/deploy-config.sh"
root=$(resolve_repo_dir config/deploy.env config/publish.env scripts/deploy.sh scripts/publish.sh)

if [ -f "$root/config/deploy.env" ] || [ -f "$root/scripts/deploy.sh" ]; then
  echo "deploy: present"
else
  echo "deploy: absent"
fi
if [ -f "$root/scripts/publish.sh" ]; then
  echo "publish: present"
else
  echo "publish: absent"
fi

deploy_type=$(deploy_get DEPLOY_TYPE "$root")
echo "deploy type: ${deploy_type:-unknown}"

# Checks the repo wants offered before a publish (SKILL.md, the ship and release offer step): one command per line, `#` comments allowed.
if [ -f "$root/.claude/pre-publish" ]; then
  grep -v '^[[:space:]]*\(#\|$\)' "$root/.claude/pre-publish" | sed 's/^/pre-publish: /'
fi
