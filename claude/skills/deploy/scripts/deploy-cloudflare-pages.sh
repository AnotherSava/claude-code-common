#!/bin/bash
# Deploy a static bundle to Cloudflare Pages via wrangler direct upload.
#
# Reads config/deploy.env (written by the deploy skill):
#   DEPLOY_TYPE=cloudflare-pages
#   CF_PAGES_PROJECT=<pages project name>
#   OUTPUT_DIR=<dir to upload, relative to repo root>   e.g. dist
#   BUILD_CMD=<command to produce OUTPUT_DIR>            e.g. node --env-file=.env scripts/build_site.mjs
#   BRANCH=<deploy branch; defaults to main>            production deploy when == production branch
#
# Secrets come from the project's gitignored .env (sourced if present):
#   CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID  — or a prior `wrangler login`
#   plus any build-time vars the BUILD_CMD needs (e.g. MAPBOX_TOKEN)
set -e

REPO_DIR="$(pwd)"
DEPLOY_ENV="$REPO_DIR/config/deploy.env"

if [ ! -f "$DEPLOY_ENV" ]; then
    echo "ERROR: config/deploy.env not found. Run the deploy skill to configure Cloudflare Pages."
    exit 1
fi

getval() { grep "^$1=" "$DEPLOY_ENV" | head -1 | cut -d= -f2-; }

CF_PAGES_PROJECT="$(getval CF_PAGES_PROJECT)"
OUTPUT_DIR="$(getval OUTPUT_DIR)"
BUILD_CMD="$(getval BUILD_CMD)"
BRANCH="$(getval BRANCH)"
BRANCH="${BRANCH:-main}"

if [ -z "$CF_PAGES_PROJECT" ]; then
    echo "ERROR: CF_PAGES_PROJECT not set in config/deploy.env"; exit 1
fi
if [ -z "$OUTPUT_DIR" ]; then
    echo "ERROR: OUTPUT_DIR not set in config/deploy.env"; exit 1
fi

# Load project secrets / build-time vars (CLOUDFLARE_API_TOKEN, account id, MAPBOX_TOKEN, ...).
if [ -f "$REPO_DIR/.env" ]; then
    echo "Loading .env ..."
    set -a; . "$REPO_DIR/.env"; set +a
fi

if [ -z "$CLOUDFLARE_API_TOKEN" ]; then
    echo "Note: CLOUDFLARE_API_TOKEN not set — relying on an existing 'wrangler login' session."
fi

if [ -n "$BUILD_CMD" ]; then
    echo "=== Build: $BUILD_CMD"
    eval "$BUILD_CMD"
    echo "Done."
else
    echo "=== No build command configured; uploading '$OUTPUT_DIR' as-is."
fi

if [ ! -d "$REPO_DIR/$OUTPUT_DIR" ]; then
    echo "ERROR: output directory '$OUTPUT_DIR' does not exist after build."; exit 1
fi

# Ensure the Pages project exists (no-op if it already does).
npx --yes wrangler pages project create "$CF_PAGES_PROJECT" --production-branch "$BRANCH" >/dev/null 2>&1 || true

echo "=== Deploying '$OUTPUT_DIR' to Cloudflare Pages project '$CF_PAGES_PROJECT' (branch: $BRANCH)..."
npx --yes wrangler pages deploy "$REPO_DIR/$OUTPUT_DIR" --project-name "$CF_PAGES_PROJECT" --branch "$BRANCH" --commit-dirty=true
echo "Deploy complete."
