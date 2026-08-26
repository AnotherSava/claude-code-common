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
#   IDENTITY_CHECK=<command>                optional — run LOCALLY after the URL checks; must exit 0
#   DOPPLER_PROJECT / DOPPLER_CONFIG        optional — render the env file before building
#   ENV_FILE=<name inside COMPOSE_DIR>      required when DOPPLER_PROJECT is set
#   VHOST_SRC=<repo-relative proxy config>  optional — the proxy config whose change forces a recreate
#   VHOST_DIR=<dir on the box>              optional — co-tenant mode: where to install VHOST_SRC.
#                                           Omit when this repo OWNS the proxy and the file is already
#                                           in the checkout — then VHOST_SRC only decides "did it change".
#   PROXY_STACK=<compose dir of the proxy>  optional — whose proxy to recreate when the config changed
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
IDENTITY_CHECK="$(getval IDENTITY_CHECK)"
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

# ── Step 3.5: identity preflight — RUNNABILITY only, never identity ──────────
# The identity check is the only thing here that can catch a host serving a neighbour's application, and it runs
# dead last: after the build, after `up -d`, and after the step-6 recreate that briefly interrupts every site the
# proxy fronts. So a manifest that cannot be resolved used to surface at the most expensive possible moment —
# every risky action already taken, and the one check that would have caught the 41-hour failure skipped.
#
# Hoisting the exit-2 condition ("this check cannot run at all") to the front makes that abort free. Only 2 is
# fatal here. Exit 1 means the host is serving the wrong app RIGHT NOW, which is frequently the very thing this
# publish exists to fix, so it must not block — identity is asserted for real after the deploy. Runnable first,
# correct last. The cost is running the check twice, a handful of GETs against pages that are already public.
if [ -n "$IDENTITY_CHECK" ]; then
    echo "=== Step 3.5: identity preflight (can the check run at all?) ==="
    PREFLIGHT_OUT="$( ( cd "$REPO_DIR" && eval "$IDENTITY_CHECK" ) 2>&1 )"; PREFLIGHT_RC=$?
    # 0 and 1 are the two verdicts a check that RAN can return; anything else — 2, or a 127 from a missing
    # interpreter or CLI — means it did not run, and is classified exactly as the post-deploy block does.
    if [ "$PREFLIGHT_RC" != 0 ] && [ "$PREFLIGHT_RC" != 1 ]; then
        echo "ERROR: the identity check cannot run (exit $PREFLIGHT_RC) — manifest unresolved, or its tooling is missing."
        printf '%s\n' "$PREFLIGHT_OUT" | sed 's/^/       /'
        echo "       NOTHING has been built or deployed; the box is untouched. Fix the check, then publish again."
        exit 1
    fi
    echo "  it runs (exit $PREFLIGHT_RC) — identity itself is asserted after the deploy"
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

# ── Step 6: the proxy config, only when it changed ───────────────────────────
# The proxy bind-mounts its config. Replacing a file there changes the inode, and a running proxy keeps reading the
# old one — `caddy reload` reports "config is unchanged" and the new vhost silently never gets a certificate.
# Recreating the container is the only thing that reliably picks it up, so it is done deliberately and only when
# the file actually changed, since it briefly interrupts every site the proxy fronts.
#
# Two shapes, distinguished by whether VHOST_DIR is set:
#   co-tenant  (VHOST_DIR set)   — this repo owns one vhost inside somebody else's proxy; install it, then recreate.
#   proxy owner (VHOST_DIR unset) — this repo owns the proxy itself, so its config is already in the checkout that
#                                   step 3 reset. Nothing to install; VHOST_SRC only answers "did it change".
if [ -n "$VHOST_SRC" ]; then
    VHOST_BASE="$(basename "$VHOST_SRC")"

    # Decide "did it change" from the BOX, not from a commit delta. Step 3 already hard-reset the box's HEAD to
    # LOCAL, so after ANY failure here the next run would compute PREV == LOCAL, skip the install, and — if a
    # previous vhost was restored — sail through step 7 and print PUBLISH OK for a publish that never installed
    # anything. Comparing the installed file to the checkout's copy cannot drift that way. It also fails safe
    # when `git diff` cannot resolve PREV at all (force-push, or a reset driven from the other machine), where
    # the old form returned empty and was read as "unchanged".
    if [ -n "$VHOST_DIR" ]; then
        LOCAL_SUM="$(shasum -a 256 "$REPO_DIR/$VHOST_SRC" 2>/dev/null | cut -d" " -f1)"
        REMOTE_SUM="$($SSH "sha256sum $VHOST_DIR/$VHOST_BASE 2>/dev/null | cut -d' ' -f1" 2>/dev/null)"
        [ -n "$LOCAL_SUM" ] && [ "$LOCAL_SUM" = "$REMOTE_SUM" ] && CHANGED=no || CHANGED=yes
    else
        CHANGED=yes
        if [ -n "$PREV" ] && [ "$PREV" != "$LOCAL" ]; then
            git diff --name-only "$PREV" "$LOCAL" -- "$VHOST_SRC" >/tmp/.vhostdiff.$$ 2>/dev/null \
                && { [ -s /tmp/.vhostdiff.$$ ] || CHANGED=no; }
            rm -f /tmp/.vhostdiff.$$
        elif [ "$PREV" = "$LOCAL" ]; then
            CHANGED=no
        fi
    fi

    if [ "$CHANGED" = yes ]; then
        if [ -n "$VHOST_DIR" ]; then
            echo "=== Step 6: installing $VHOST_BASE and recreating $PROXY_SERVICE ==="
            # VALIDATION IS MANDATORY WHENEVER WE WRITE INTO THE SHARED DIRECTORY, not merely when we also
            # recreate. The proxy imports every tenant's file, so one bad or conflicting vhost makes the WHOLE
            # config unparseable — and it goes live at the proxy's next START, not the next reload, so an
            # install-only publish just plants the failure for whoever restarts next. Two files claiming one
            # site address is enough ("ambiguous site definition"). Refusing to install unvalidated is the
            # point; a config with no way to check it is not a safer place to leave a file.
            if [ -z "$PROXY_STACK" ]; then
                echo "ERROR: VHOST_DIR is set but PROXY_STACK is not, so the installed vhost cannot be validated."
                echo "       Set PROXY_STACK to the proxy's compose dir. Installing into a shared conf.d without"
                echo "       validating is what takes every co-tenant down at the proxy's next start."
                exit 1
            fi
            # PRECONDITIONS, checked BEFORE the shared directory is touched — a failure that never writes is
            # strictly better than one that writes and reverts.
            #   1. the proxy must be up, or nothing can be validated;
            #   2. the config being validated must be OURS. The stock caddy image ships a placeholder
            #      /etc/caddy/Caddyfile (":80 { root * /usr/share/caddy; file_server }"), so if the bind mount
            #      is ever missing, `caddy validate` happily returns 0 against the welcome page — a green check
            #      on a config that imports nothing and would serve a placeholder for every hostname. Requiring
            #      the conf.d import proves both that the real file is mounted and that what we install is even
            #      visible to it.
            if [ -z "$($SSH "cd $PROXY_STACK && docker compose ps --status running -q $PROXY_SERVICE" 2>/dev/null)" ]; then
                echo "ERROR: $PROXY_SERVICE is not running, so the vhost cannot be validated — nothing installed."
                echo "       Start the proxy and re-run."
                exit 1
            fi
            # Capture the imported path, do not just confirm one exists: it is the CONTAINER path, while VHOST_DIR
            # is a HOST path, and nothing else in this script connects the two. That gap is the same bug in a new
            # costume — with a mistyped or host-divergent VHOST_DIR every check here passes, the file lands in a
            # directory nothing reads, validate passes because the config genuinely did not change, and VERIFY_URL
            # answers 200 from the vhost that was already there. PUBLISH OK for a publish that installed nothing,
            # and the sha256 compare above can never match, so it reinstalls forever without converging.
            IMPORT_LINE="$($SSH "cd $PROXY_STACK && docker compose exec -T $PROXY_SERVICE grep -m1 -E '^[[:space:]]*import[[:space:]]+[^[:space:]]*conf\.d' /etc/caddy/Caddyfile" 2>/dev/null)"
            CONF_D_IN="$(printf '%s' "$IMPORT_LINE" | awk '{print $2}' | sed 's:/[^/]*$::')"
            if [ -z "$CONF_D_IN" ]; then
                echo "ERROR: the proxy's live /etc/caddy/Caddyfile does not import a conf.d directory."
                echo "       Either the base config is not bind-mounted (the caddy image ships a placeholder that"
                echo "       validates green) or it does not import $VHOST_DIR at all — installing would be invisible."
                exit 1
            fi
            PREV_F="$VHOST_DIR/.$VHOST_BASE.prev"
            LIVE_F="$VHOST_DIR/$VHOST_BASE"
            RESTORE="if [ -f $PREV_F ]; then mv -f $PREV_F $LIVE_F; else rm -f $LIVE_F; fi"
            VALIDATE="cd $PROXY_STACK && docker compose exec -T $PROXY_SERVICE caddy validate --config /etc/caddy/Caddyfile"
            RUNNING="cd $PROXY_STACK && docker compose ps --status running -q $PROXY_SERVICE"

            # Back up EXPLICITLY. An `|| true` here cannot tell "there was no previous file" from "cp failed",
            # and a swallowed cp leaves RESTORE with nothing to restore — so a later failure would delete the
            # tenant's working vhost while reporting that it put it back.
            $SSH "mkdir -p $VHOST_DIR && rm -f $PREV_F && if [ -f $LIVE_F ]; then cp -p $LIVE_F $PREV_F; fi" \
                || { echo "ERROR: could not prepare $VHOST_DIR / back up the existing vhost"; exit 1; }

            # Write to a temp name and mv into place: `>` truncates before the first byte arrives, so a dropped
            # connection mid-transfer would otherwise leave a half-written vhost — unbalanced braces are enough
            # to make the whole shared config unparseable. mv within one directory is atomic, so the live file
            # is never partial.
            if ! $SSH "cat > $LIVE_F.tmp" < "$REPO_DIR/$VHOST_SRC"; then
                $SSH "rm -f $LIVE_F.tmp $PREV_F"
                echo "ERROR: could not transfer the vhost — nothing was replaced."
                exit 1
            fi
            $SSH "mv -f $LIVE_F.tmp $LIVE_F" \
                || { $SSH "rm -f $LIVE_F.tmp"; echo "ERROR: could not install the vhost"; exit 1; }
            # The bytes are on the host; prove the proxy can actually see them. This is what ties VHOST_DIR to the
            # directory the config imports — without it a wrong VHOST_DIR is indistinguishable from success.
            if ! $SSH "cd $PROXY_STACK && docker compose exec -T $PROXY_SERVICE test -f $CONF_D_IN/$VHOST_BASE" >/dev/null 2>&1; then
                $SSH "$RESTORE" || echo "       (restore also failed — check $LIVE_F by hand)"
                echo "ERROR: installed $VHOST_BASE is not visible to the proxy at $CONF_D_IN."
                echo "       VHOST_DIR ($VHOST_DIR) is a HOST path and does not map to the directory the proxy"
                echo "       imports. The file would sit where nothing reads it, and every check below would pass."
                exit 1
            fi

            # Distinguish THREE outcomes, not two: valid, invalid, and could-not-check. They share exit 1, and
            # blaming a tenant's vhost for a stopped proxy or a dead network would strand it with no config.
            if ! VALIDATE_OUT="$($SSH "$VALIDATE" 2>&1)"; then
                if ! $SSH true >/dev/null 2>&1; then
                    echo "ERROR: lost the connection to $SSH_HOST after installing $VHOST_BASE."
                    echo "       The shared config dir is in an UNKNOWN state — $LIVE_F may hold an unvalidated"
                    echo "       vhost. Restore it by hand before the proxy is next started:"
                    echo "         $RESTORE"
                    exit 1
                fi
                if [ -z "$($SSH "$RUNNING" 2>/dev/null)" ]; then
                    $SSH "$RESTORE" || { echo "ERROR: could not restore $LIVE_F — do it by hand: $RESTORE"; exit 1; }
                    echo "ERROR: $PROXY_SERVICE is not running, so the config could not be validated — restored"
                    echo "       the previous vhost and stopped. This is NOT a verdict on $VHOST_BASE; start the"
                    echo "       proxy and re-run."
                    exit 1
                fi
                $SSH "$RESTORE" || { echo "ERROR: could not restore $LIVE_F — do it by hand: $RESTORE"; exit 1; }
                echo "ERROR: proxy config does not validate with $VHOST_BASE installed — restored the previous state."
                echo "$VALIDATE_OUT" | sed "s/^/       caddy: /"
                if $SSH "$VALIDATE" >/dev/null 2>&1; then
                    echo "       Valid again without it, so the fault is in this repo's vhost."
                else
                    echo "       STILL invalid without it — pre-existing breakage, and not this repo's to chase."
                fi
                exit 1
            fi
            $SSH "rm -f $PREV_F" || true
        else
            echo "=== Step 6: $VHOST_BASE changed in the checkout — recreating $PROXY_SERVICE ==="
        fi
        if [ -n "$PROXY_STACK" ]; then
            $SSH "cd $PROXY_STACK && docker compose up -d --force-recreate $PROXY_SERVICE" \
                || { echo "ERROR: could not recreate $PROXY_SERVICE"; exit 1; }
        fi
    else
        echo "=== Step 6: $VHOST_BASE unchanged — leaving $PROXY_SERVICE alone ==="
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

# A 200 says something is serving, not that it is OURS. Where one box hosts several projects behind one proxy, a
# name collision can route this host at a neighbour's app, which answers 200 just as healthily — a storefront once
# served the wrong application for 41 hours with every check above green. IDENTITY_CHECK is where a project asserts
# the response really is its own. Run from HERE, never on the box: a checker on the box shares fate with the thing
# it is checking.
#
# WRONG-APP and COULD-NOT-CHECK both fail the publish, but they must not SAY the same thing, because the wording
# is what an operator acts on. Collapsing them meant a missing manifest, an expired token or a dead network all
# announced "this host may be serving another app" — in the scariest available wording, moments after step 6
# recreated the proxy and briefly interrupted every site it fronts. Beginning an emergency rollback over a file
# that failed to download is a rational response to that sentence. It is the same distinction step 6 already
# draws between "config invalid" and "proxy is down", and it is drawn here for the same reason.
if [ -n "$IDENTITY_CHECK" ]; then
    echo "  identity: $IDENTITY_CHECK"
    ( cd "$REPO_DIR" && eval "$IDENTITY_CHECK" ); IDENTITY_RC=$?
    case "$IDENTITY_RC" in
        0) ;;
        1) echo "  IDENTITY CHECK FAILED — this host may be serving another app"
           OK=1 ;;
        *) echo "  IDENTITY CHECK COULD NOT RUN (exit $IDENTITY_RC) — nothing was asserted about what this host serves"
           echo "  This is a tooling failure, NOT evidence of a misroute. Do not roll back on this alone."
           OK=1 ;;
    esac
fi

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
