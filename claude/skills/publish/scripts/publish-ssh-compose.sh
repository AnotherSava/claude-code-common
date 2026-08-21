#!/bin/bash
# Publish a Dockerised app to a box you control, over SSH. The outward counterpart to `deploy`, which only makes
# the code runnable here.
#
# Shape it assumes: the box holds a git checkout of this repo, a compose stack built from that checkout, and a
# reverse proxy that fronts it. The app publishes no host port — it is reached through the proxy — so this script
# can also install the vhost the app owns and restart the proxy when that file changed.
#
# Reads config/publish.env (written by the publish skill):
#   PUBLISH_TYPE=ssh-compose
#   SSH_HOST=<user@host>                    required
#   REMOTE_REPO=<path to the checkout>      required — reconciled to origin/<branch> with a hard reset
#   REPO_URL=<url the BOX clones from>      required only for the first publish (often an ssh alias)
#   COMPOSE_DIR=<dir holding compose.yml>   required
#   BUILD_SERVICES=<space-separated>        default: app
#   APP_CONTAINER=<container name>          required — for the restart-count check
#   VERIFY_URL=<https://host/path>          required — a real user-facing page, not a health endpoint
#   VERIFY_URL_EXTRA=<second URL>           optional
#   DOPPLER_PROJECT / DOPPLER_CONFIG        optional — render the env file before building
#   ENV_FILE=<name inside COMPOSE_DIR>      required when DOPPLER_PROJECT is set
#   VHOST_SRC=<repo-relative .caddy file>   optional — the vhost this app owns
#   VHOST_DIR=<dir on the box>              optional — where co-tenant vhosts are imported from
#   PROXY_STACK=<compose dir of the proxy>  optional — whose proxy to recreate when the vhost changed
#   PROXY_SERVICE=<service name>            default: caddy
#   SETTLE_SECONDS=<seconds>                default: 25
#   BRANCH=<branch>                         default: main
#
# Publishes only committed, pushed code. Never bumps a version or creates a tag — that is the `release` verb.
set -uo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_repo-dir.sh"
REPO_DIR="$(resolve_repo_dir)"
ENV_PATH="$REPO_DIR/config/publish.env"
if [ ! -f "$ENV_PATH" ]; then
    echo "ERROR: no config/publish.env found (looked upward from $PWD, settled on $REPO_DIR)."
    echo "       Run the publish skill to write one, or check you are inside the right repo."
    exit 1
fi
getval() { grep "^$1=" "$ENV_PATH" | head -1 | cut -d= -f2- || true; }

SSH_HOST="$(getval SSH_HOST)"
REMOTE_REPO="$(getval REMOTE_REPO)"
COMPOSE_DIR="$(getval COMPOSE_DIR)"
APP_CONTAINER="$(getval APP_CONTAINER)"
VERIFY_URL="$(getval VERIFY_URL)"

# Validated here, not inside a helper: `exit` within a $( ) substitution ends the SUBSHELL, so a missing key would
# print its error into the variable and the script would sail on to try and publish with a blank host. Report every
# missing key at once rather than one per run.
MISSING=""
for k in SSH_HOST REMOTE_REPO COMPOSE_DIR APP_CONTAINER VERIFY_URL; do
    [ -n "${!k}" ] || MISSING="$MISSING $k"
done
if [ -n "$MISSING" ]; then
    echo "ERROR: config/publish.env is missing:$MISSING"
    exit 1
fi

REPO_URL="$(getval REPO_URL)"
BUILD_SERVICES="$(getval BUILD_SERVICES)"; BUILD_SERVICES="${BUILD_SERVICES:-app}"
VERIFY_URL_EXTRA="$(getval VERIFY_URL_EXTRA)"
DOPPLER_PROJECT="$(getval DOPPLER_PROJECT)"
DOPPLER_CONFIG="$(getval DOPPLER_CONFIG)"
ENV_FILE="$(getval ENV_FILE)"
VHOST_SRC="$(getval VHOST_SRC)"
VHOST_DIR="$(getval VHOST_DIR)"
PROXY_STACK="$(getval PROXY_STACK)"
PROXY_SERVICE="$(getval PROXY_SERVICE)"; PROXY_SERVICE="${PROXY_SERVICE:-caddy}"
SETTLE_SECONDS="$(getval SETTLE_SECONDS)"; SETTLE_SECONDS="${SETTLE_SECONDS:-25}"
BRANCH="$(getval BRANCH)"; BRANCH="${BRANCH:-main}"

SSH="ssh -o BatchMode=yes -o ConnectTimeout=15 $SSH_HOST"
cd "$REPO_DIR" || exit 1

# ── Step 1: only ever ship committed, pushed code ────────────────────────────
# A working tree that differs from origin means the box would run something no commit describes. This is the one
# guard that cannot be waived: everything downstream reconciles the box TO a commit, so there must be one.
echo "=== Step 1: checking the working tree ==="
if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: uncommitted changes. Publish ships commits, not a working tree."
    git status --short
    exit 1
fi
git fetch -q origin "$BRANCH" 2>/dev/null
LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse "origin/$BRANCH" 2>/dev/null)"
if [ "$LOCAL" != "$REMOTE" ]; then
    echo "ERROR: HEAD is not origin/$BRANCH. Push first — the box pulls from the remote, not from here."
    git log --oneline "origin/$BRANCH..HEAD" 2>/dev/null | sed 's/^/  unpushed: /'
    exit 1
fi
echo "  clean, and HEAD matches origin/$BRANCH (${LOCAL:0:8})"

# What changed since the box's current commit — decides whether the vhost needs reinstalling below.
PREV="$($SSH "cd $REMOTE_REPO && git rev-parse HEAD" 2>/dev/null)"

# ── Step 2: reconcile the box ────────────────────────────────────────────────
# Hard reset, never merge: the box is a checkout, not a place work happens. A merge there would create a commit
# that exists nowhere else.
#
# Clone if it isn't there yet, so the first publish behaves like every later one rather than failing on a
# missing directory. REPO_URL is separate from the local `origin` because the box usually reaches a private
# repo through its own deploy key, addressed by an ssh_config alias — a deploy key is scoped to ONE repository,
# so a box hosting several apps needs one key and one alias each.
if ! $SSH "test -d $REMOTE_REPO/.git"; then
    echo "=== Step 2: no checkout at $REMOTE_REPO — cloning ==="
    [ -n "$REPO_URL" ] || {
        echo "ERROR: $REMOTE_REPO does not exist and REPO_URL is not set in config/publish.env."
        echo "       Set REPO_URL to the URL the BOX should clone from (often an ssh_config alias, not origin)."
        exit 1
    }
    $SSH "git clone -q --branch $BRANCH $REPO_URL $REMOTE_REPO && cd $REMOTE_REPO && git rev-parse --short HEAD" \
        || { echo "ERROR: clone failed. Can the box read $REPO_URL?"; exit 1; }
else
    echo "=== Step 2: reconciling $REMOTE_REPO to origin/$BRANCH ==="
    $SSH "cd $REMOTE_REPO && git fetch origin -q && git reset --hard origin/$BRANCH -q && git rev-parse --short HEAD" \
        || { echo "ERROR: could not reconcile the checkout"; exit 1; }
fi

# ── Step 3: render secrets straight onto the box ─────────────────────────────
# Piped over SSH so the values never reach this terminal, the transcript, or shell history. umask 077 so the file
# is not world-readable even for the instant before compose reads it.
if [ -n "$DOPPLER_PROJECT" ]; then
    [ -n "$ENV_FILE" ] || { echo "ERROR: ENV_FILE is required when DOPPLER_PROJECT is set"; exit 1; }
    echo "=== Step 3: rendering $ENV_FILE from Doppler $DOPPLER_PROJECT/$DOPPLER_CONFIG ==="
    doppler secrets download -p "$DOPPLER_PROJECT" -c "$DOPPLER_CONFIG" --format env --no-file \
        | $SSH "umask 077; cat > $COMPOSE_DIR/$ENV_FILE" \
        || { echo "ERROR: could not render the env file"; exit 1; }
    echo "  wrote $COMPOSE_DIR/$ENV_FILE ($(  $SSH "wc -l < $COMPOSE_DIR/$ENV_FILE" ) keys)"
else
    echo "=== Step 3: no Doppler project configured — skipping env render ==="
fi

# ── Step 4: build, detached ──────────────────────────────────────────────────
# A compose build routinely runs 5-25 minutes, which outlives the tool timeout that invokes this script. setsid
# detaches it from the SSH session so it survives, and the log is polled instead of the command being waited on.
echo "=== Step 4: building [$BUILD_SERVICES] (detached; polling the log) ==="
BUILD_LOG="/tmp/publish-build-$(date +%s).log"
$SSH "cd $COMPOSE_DIR && setsid sh -c 'docker compose build $BUILD_SERVICES >$BUILD_LOG 2>&1; echo EXIT=\$? >>$BUILD_LOG' </dev/null >/dev/null 2>&1 & echo started" \
    || { echo "ERROR: could not start the build"; exit 1; }

for i in $(seq 1 180); do   # 180 x 10s = 30 minutes
    sleep 10
    TAIL="$($SSH "tail -c 4000 $BUILD_LOG 2>/dev/null" || true)"
    case "$TAIL" in
        *EXIT=0*) echo "  build finished"; break ;;
        *EXIT=*)  echo "ERROR: build failed. Last lines:"; printf '%s\n' "$TAIL" | tail -25; exit 1 ;;
    esac
    [ $((i % 6)) -eq 0 ] && echo "  still building ($((i / 6)) min)"
    [ "$i" = 180 ] && { echo "ERROR: build did not finish in 30 minutes; log: $SSH_HOST:$BUILD_LOG"; exit 1; }
done

# ── Step 5: start it ─────────────────────────────────────────────────────────
echo "=== Step 5: bringing the stack up ==="
$SSH "cd $COMPOSE_DIR && docker compose up -d" || { echo "ERROR: compose up failed"; exit 1; }

# ── Step 6: the vhost, only when it changed ──────────────────────────────────
# The proxy bind-mounts its config directory. Replacing a file there changes the inode, and a running proxy keeps
# reading the old one — `caddy reload` reports "config is unchanged" and the new vhost silently never gets a
# certificate. Recreating the container is the only thing that reliably picks it up, so it is done deliberately
# and only when the file actually changed, since it briefly interrupts every site the proxy fronts.
if [ -n "$VHOST_SRC" ] && [ -n "$VHOST_DIR" ]; then
    CHANGED=yes
    if [ -n "$PREV" ] && [ "$PREV" != "$LOCAL" ]; then
        git diff --name-only "$PREV" "$LOCAL" -- "$VHOST_SRC" | grep -q . || CHANGED=no
    elif [ "$PREV" = "$LOCAL" ]; then
        CHANGED=no
    fi
    if [ "$CHANGED" = yes ]; then
        echo "=== Step 6: installing $(basename "$VHOST_SRC") and recreating $PROXY_SERVICE ==="
        $SSH "mkdir -p $VHOST_DIR" && $SSH "cat > $VHOST_DIR/$(basename "$VHOST_SRC")" < "$REPO_DIR/$VHOST_SRC" \
            || { echo "ERROR: could not install the vhost"; exit 1; }
        if [ -n "$PROXY_STACK" ]; then
            $SSH "cd $PROXY_STACK && docker compose up -d --force-recreate $PROXY_SERVICE" \
                || { echo "ERROR: could not recreate $PROXY_SERVICE"; exit 1; }
        fi
    else
        echo "=== Step 6: vhost unchanged — leaving $PROXY_SERVICE alone ==="
    fi
fi

# ── Step 7: prove it serves ──────────────────────────────────────────────────
# A green build and a running container prove nothing. A health probe proves little more: one has passed while
# every database-backed page returned 502. Assert a real page AND that the container is not restarting — a
# crash-looping app answers 200 between restarts.
echo "=== Step 7: verifying (settling ${SETTLE_SECONDS}s) ==="
sleep "$SETTLE_SECONDS"
RESTARTS="$($SSH "docker inspect $APP_CONTAINER --format '{{.RestartCount}}'" 2>/dev/null)"
STATUS="$($SSH "docker inspect $APP_CONTAINER --format '{{.State.Status}}'" 2>/dev/null)"
echo "  container: status=$STATUS restarts=$RESTARTS"

check_url() {
    local url="$1" code
    for attempt in 1 2 3 4 5 6; do
        code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$url" 2>/dev/null || echo 000)"
        [ "$code" = "200" ] && { echo "  $url -> 200"; return 0; }
        [ "$attempt" != 6 ] && { echo "  attempt $attempt: $url -> $code, waiting"; sleep 10; }
    done
    echo "  $url -> $code"
    return 1
}

OK=0
check_url "$VERIFY_URL" || OK=1
[ -n "$VERIFY_URL_EXTRA" ] && { check_url "$VERIFY_URL_EXTRA" || OK=1; }

# Re-read the counter: a container that crash-looped during verification climbs here even if a request slipped
# through between restarts.
RESTARTS_AFTER="$($SSH "docker inspect $APP_CONTAINER --format '{{.RestartCount}}'" 2>/dev/null)"
[ "$RESTARTS_AFTER" != "$RESTARTS" ] && { echo "  restarts climbed $RESTARTS -> $RESTARTS_AFTER"; OK=1; }
[ "$STATUS" = "running" ] || OK=1

if [ "$OK" = 0 ]; then
    echo "PUBLISH OK  ($SSH_HOST, ${LOCAL:0:8})"
else
    echo "PUBLISH FAILED — the stack is up but is not serving correctly."
    echo "  logs: ssh $SSH_HOST 'cd $COMPOSE_DIR && docker compose logs --tail 80 $APP_CONTAINER'"
    exit 1
fi
