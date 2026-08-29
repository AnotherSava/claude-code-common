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
#   VHOST_SRC=<repo-relative proxy config>  optional — this repo's vhost / proxy config
#   VHOST_GATE=<gate path on the box>       default: /opt/landlord/bin/vhost-install
#
#   When the box has an executable at VHOST_GATE, that gate installs the vhost and the next three keys are
#   NOT read at all — the host knows its own compose dir, its own proxy, and where vhosts live, so a tenant
#   holding that knowledge is three chances to hold a stale copy of it. Delete them from a gated host's
#   config. They remain required on an ungated box, where this script is still the only writer:
#
#   VHOST_DIR=<dir on the box>              ungated co-tenant mode: where to install VHOST_SRC.
#                                           Omit when this repo OWNS the proxy and the file is already
#                                           in the checkout — then VHOST_SRC only decides "did it change".
#   PROXY_STACK=<compose dir of the proxy>  ungated — whose proxy to recreate when the config changed
#   PROXY_SERVICE=<service name>            ungated — default: caddy
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
# The host's vhost gate, if the box has one. Defaulted rather than required, so a landlord-managed box needs NO
# new key in any tenant's config — which matters because these configs are per-machine and gitignored, so every
# added key is an edit on several machines that git cannot show you is half done.
VHOST_GATE="$(getval VHOST_GATE)"; VHOST_GATE="${VHOST_GATE:-/opt/landlord/bin/vhost-install}"
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

# ── Where the identity check comes from ──────────────────────────────────────
# IDENTITY_CHECK used to be ~700 characters of shell copied BYTE-IDENTICALLY into every tenant's per-machine,
# gitignored config. Nothing in it was ever about the tenant — it resolves the checker, obtains the host's
# manifest, and classifies could-not-check. It changed four times in one week, and each change meant hand-editing
# every tenant on every machine. The one time that was done unevenly, a tenant was left pointing at a path that
# no longer existed; nothing in the system would have reported it. Host machinery does not belong in per-tenant
# config, so the host supplies it — the same argument as VHOST_GATE, and the same shape.
HOST_MANIFEST="$(getval HOST_MANIFEST)"; HOST_MANIFEST="${HOST_MANIFEST:-/opt/landlord/bin/host-manifest}"
# Where the host records which hostnames each tenant may serve. The glob is expanded by the REMOTE shell.
HOST_GRANTS="$(getval HOST_GRANTS)"; HOST_GRANTS="${HOST_GRANTS:-/opt/landlord/hosts/*/tenants}"

# ONE round trip, both host facilities. The gate probe is HOISTED here from step 6 — not for tidiness, but
# because the shared-box test below needs it and step 6 runs after the build. Asking the BOX what it is beats
# asking a key the tenant may never set.
HOST_PROBE="$($SSH "test -x $HOST_MANIFEST && echo hm=yes || echo hm=no; test -x $VHOST_GATE && echo gate=yes || echo gate=no" 2>/dev/null)"
[ -n "$HOST_PROBE" ] || { echo "ERROR: could not reach $SSH_HOST to probe for the host's publish facilities."; exit 1; }
HM_PRESENT="$(printf '%s\n' "$HOST_PROBE" | sed -n 's/^hm=//p')"
GATE_PRESENT="$(printf '%s\n' "$HOST_PROBE" | sed -n 's/^gate=//p')"

IDENTITY_SOURCE=none
if [ -n "$IDENTITY_CHECK" ]; then
    IDENTITY_SOURCE="configured IDENTITY_CHECK"
    # A local value SHADOWING a host default is the drift this change exists to end, and it is invisible by
    # construction: the override works, so nothing fails and nobody looks. That is exactly how one tenant was
    # left pointing at a deleted path while its neighbour had been updated. An override is legitimate — say so
    # rather than fail — but say it every publish, so "still overriding" is a decision and not an oversight.
    [ "$HM_PRESENT" = yes ] && {
        echo "NOTE: this box supplies an identity check at $HOST_MANIFEST, and config/publish.env overrides it."
        echo "      Host machinery in per-tenant config drifts: it is unversioned, per-machine, and has to be"
        echo "      re-edited by hand for every tenant on every machine each time the host form changes."
        echo "      Unless this project genuinely needs its own, remove IDENTITY_CHECK and inherit the default."
    }
elif [ "$HM_PRESENT" = yes ]; then
    IDENTITY_SOURCE="host ($HOST_MANIFEST)"
fi

# THE FALLBACK IS NOT SYMMETRIC WITH VHOST_GATE'S, and must not be written as if it were. VHOST_GATE may degrade
# to the old copy-and-reload path because that path still works. Degrading to "no identity check" is the exact
# thing this system exists to forbid: could-not-check, reported as fine, in the one check that exists because a
# storefront served a neighbour's application for 41 hours. So on a box that is demonstrably SHARED and offers no
# host default, refuse rather than skip — "no identity check" has to be something a person typed.
#
# The predicate is "is this box shared", NOT "is the host default missing". Those differ, and the difference
# matters: most projects using this script are alone on their box and have no identity question to answer.
# Failing them would make the rule unkeepable, and an unkeepable rule gets deleted rather than obeyed.
#
# THE GATE IS THE LOAD-BEARING SIGNAL, and the first version of this guard was wrong without it. It tested only
# VHOST_DIR and PROXY_STACK — and the gated tenants set NEITHER, because the absence of VHOST_DIR is exactly what
# routes them through the gate. So on the one box this whole system exists for, the shared-box test evaluated
# false for every tenant on it. It was moot only while the host default resolved; the hole opened precisely when
# the guard was needed — host-manifest renamed, moved, or the landlord checkout behind — and would then have
# built, deployed and recreated the SHARED proxy with no identity assertion at all, silently. A box carrying an
# executable gate IS a shared box, and that fact is read from the box rather than from config a tenant may never
# write. Solo boxes have no gate, so they still continue untouched.
# Name the disjunct that ACTUALLY fired. One sentence covering three causes sends the operator to whichever the
# author happened to write down: on a gated box no tenant sets VHOST_DIR or PROXY_STACK, so a message naming
# those two would point at keys that are unset and always were, while the real reason went unmentioned.
SHARED_WHY=""
[ "$GATE_PRESENT" = yes ] && SHARED_WHY="a vhost gate exists at $VHOST_GATE"
[ -n "$VHOST_DIR" ]       && SHARED_WHY="${SHARED_WHY:+$SHARED_WHY; }VHOST_DIR is set ($VHOST_DIR)"
[ -n "$PROXY_STACK" ]     && SHARED_WHY="${SHARED_WHY:+$SHARED_WHY; }PROXY_STACK is set ($PROXY_STACK)"

if [ "$IDENTITY_SOURCE" = none ] && [ -n "$SHARED_WHY" ]; then
    echo "ERROR: this box is shared — $SHARED_WHY — but nothing can assert what it serves."
    echo "       No IDENTITY_CHECK is configured and no host default exists at $HOST_MANIFEST."
    echo "       A 200 from a shared proxy does not prove the response is yours. Either restore the host"
    echo "       default, or set IDENTITY_CHECK in config/publish.env — the publish skill carries the"
    echo "       portable form. NOTHING has been built or deployed."
    exit 1
fi

# ── VERIFY_URL must name something this tenant was GRANTED ───────────────────
# Step 7 proves VERIFY_URL serves. It cannot notice that VERIFY_URL was never this tenant's hostname to verify —
# a publish would then assert a neighbour's site is healthy and call that its own success. The way that happens
# is not exotic: these configs are per-machine, gitignored and routinely hand-copied between tenants, which is
# the same mechanism that produced everything else in this file. The host already knows who owns what.
#
# Fail only when the grants ARE readable and the host is absent from them. Unreadable grants are could-not-check
# and must not fail the publish, or a host-side layout change starts blocking every tenant's deploy.
if [ "$GATE_PRESENT" = yes ] && [ -n "$VHOST_SRC" ]; then
    GRANT_PROJECT="$(basename "$VHOST_SRC")"; GRANT_PROJECT="${GRANT_PROJECT%.*}"
    GRANTS="$($SSH "cat $HOST_GRANTS/$GRANT_PROJECT.owns 2>/dev/null" 2>/dev/null | grep -v '^[[:space:]]*#' | grep -v '^[[:space:]]*$')"
    if [ -n "$GRANTS" ]; then
        for _u in "$VERIFY_URL" $VERIFY_URL_EXTRA; do
            [ -n "$_u" ] || continue
            _host="$(printf '%s' "$_u" | sed -e 's#^[a-zA-Z]*://##' -e 's#[/:?].*##')"
            printf '%s\n' "$GRANTS" | grep -qx "$_host" || {
                echo "ERROR: '$_host' is not a hostname this host grants to '$GRANT_PROJECT'."
                echo "       Verifying it would assert somebody else's site is healthy and report that as this"
                echo "       publish succeeding. Either VERIFY_URL is wrong, or the grant is missing."
                echo "       Granted: $(printf '%s' "$GRANTS" | tr '\n' ' ')"
                echo "       NOTHING has been built or deployed."
                exit 1
            }
        done
        echo "  grants: VERIFY_URL host(s) are granted to $GRANT_PROJECT"
    else
        echo "  grants: could not read $HOST_GRANTS/$GRANT_PROJECT.owns — VERIFY_URL was NOT checked against"
        echo "          the host's grants. Not a verdict; nothing here says the hostname is wrong."
    fi
fi

# One implementation, used by BOTH the preflight and the post-deploy check. Two call sites that classify or
# obtain differently is how a preflight comes to wave through what the final check condemns.
identity_run() {
    if [ -n "$IDENTITY_CHECK" ]; then
        ( cd "$REPO_DIR" && eval "$IDENTITY_CHECK" ); return $?
    fi
    _ck="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/identity-check.py"
    # ~/.claude/scripts is a Git-Bash symlink on Windows and native programs cannot traverse it (Errno 22).
    _ck="$(readlink -f "$_ck" 2>/dev/null || echo "$_ck")"
    [ -f "$_ck" ] || { echo "  IDENTITY CHECKER NOT FOUND at $_ck — the check NEVER RAN; this is NOT an impersonation."; return 2; }
    # A real relative file, not process substitution: <(...) is /proc/PID/fd/N, which native Windows python
    # cannot open. The HTTP probes still run from HERE — only the manifest comes from the box, because a
    # checker that runs on the box shares fate with the thing it is checking.
    _mf="$REPO_DIR/.identity-manifest.$$.json"
    if ! $SSH "$HOST_MANIFEST" > "$_mf" 2>"$_mf.err" || [ ! -s "$_mf" ]; then
        echo "  COULD NOT OBTAIN THE MANIFEST from $HOST_MANIFEST — the check NEVER RAN; NOT an impersonation."
        tr -s '[:space:]' ' ' < "$_mf.err" 2>/dev/null | cut -c1-120 | sed 's/^/    /'
        rm -f "$_mf" "$_mf.err"; return 2
    fi
    python3 "$_ck" "$_mf"; _rc=$?
    # Capture BEFORE the cleanup and return it explicitly: without this the status is `rm -f`'s, always 0, so a
    # failed identity check would report success.
    rm -f "$_mf" "$_mf.err"
    return $_rc
}

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
if [ "$IDENTITY_SOURCE" != none ]; then
    echo "=== Step 3.5: identity preflight (can the check run at all?) — source: $IDENTITY_SOURCE ==="
    PREFLIGHT_OUT="$(identity_run 2>&1)"; PREFLIGHT_RC=$?
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
#
# WHERE THE BOX HAS A GATE, THE GATE DOES ALL OF IT. Everything below this branch — deciding "did it change",
# backing up, writing, validating, rolling back, recreating — is this script doing a shared directory's job from
# the outside, which is only correct while it is the ONLY writer. On a host that governs its own conf.d it is
# not, and validating from out here means every rule the host publishes is advisory on the exact path every
# tenant actually uses. So: ask the host, and let it refuse. It validates in a container of the running image
# BEFORE the write and rolls back a failed reload, neither of which a caller can do for it.
# GATE_PRESENT was probed before the build, alongside HOST_MANIFEST, in one round trip. It is deliberately not
# re-probed here: the same fact answered twice can answer differently, and the earlier probe already refuses to
# read an unreachable box as "no gate" — that guess would write into a directory the host believes it governs.
if [ -n "$VHOST_SRC" ] && [ "$GATE_PRESENT" = yes ]; then
    VHOST_BASE="$(basename "$VHOST_SRC")"
    echo "=== Step 6: handing $VHOST_BASE to the host's gate ($VHOST_GATE) ==="

    # A private scratch DIRECTORY, because the basename must survive: the gate derives the project from it, and
    # that derivation is an assertion (it must match a tenants/<project>.owns the host wrote), not a convenience.
    # Renaming the candidate to something unique would quietly defeat the check it exists to make.
    GATE_TMP="/tmp/vhost-publish-$$"
    $SSH "mkdir -p $GATE_TMP" || { echo "ERROR: could not create $GATE_TMP on the box"; exit 1; }
    if ! $SSH "cat > $GATE_TMP/$VHOST_BASE" < "$REPO_DIR/$VHOST_SRC"; then
        $SSH "rm -rf $GATE_TMP"
        echo "ERROR: could not copy $VHOST_BASE to the box — nothing was offered to the gate."
        exit 1
    fi

    GATE_ERR="$(mktemp)"
    GATE_TOKEN="$($SSH "$VHOST_GATE $GATE_TMP/$VHOST_BASE" 2>"$GATE_ERR")"; GATE_RC=$?
    $SSH "rm -rf $GATE_TMP" || true
    [ -s "$GATE_ERR" ] && sed 's/^/       /' "$GATE_ERR"
    rm -f "$GATE_ERR"

    # `rollback-incomplete` is checked FIRST and independently of the status, because it is the one token that
    # says the box was left in a state nobody asked for — the file is back but the running config is not. It
    # must not be filed under whichever exit code happens to carry it.
    if [ "$GATE_TOKEN" = rollback-incomplete ]; then
        echo "  VHOST ROLLBACK INCOMPLETE — the box is NOT in a known state."
        echo "  The candidate was withdrawn but the running proxy config was not reconciled, so what is"
        echo "  serving now may match neither the old vhost nor the new one. Read the gate's output above"
        echo "  and reconcile by hand; do not re-run this publish until it is resolved."
        exit 1
    fi

    case "$GATE_RC" in
        0) case "$GATE_TOKEN" in
               unchanged) echo "  gate: unchanged — the installed vhost already matches; proxy untouched" ;;
               installed) echo "  gate: installed — validated against the running image, and reloaded" ;;
               *)         echo "  gate: reported '$GATE_TOKEN'" ;;
           esac ;;
        1) echo "  VHOST REFUSED — the gate rejected $VHOST_BASE (token: ${GATE_TOKEN:-none})."
           echo "  This IS a verdict on this repo's vhost: it is invalid, or it was applied and rolled back."
           echo "  Nothing on the box was left changed. Fix the vhost in this repo and publish again."
           exit 1 ;;
        2) echo "  VHOST GATE COULD NOT CHECK (token: ${GATE_TOKEN:-none}) — lock held, proxy down, or a layer"
           echo "  missing. This is NOT a rejection of $VHOST_BASE and says nothing about whether it is valid."
           echo "  Whether anything was attempted is in the gate's output above. Fix the host-side condition"
           echo "  and re-run; do not start editing the vhost on the strength of this."
           exit 1 ;;
        *) echo "  VHOST GATE FAILED TO RUN (exit $GATE_RC, token: ${GATE_TOKEN:-none}) — treat as could-not-check,"
           echo "  not as a rejection. The gate did not reach a verdict on $VHOST_BASE."
           exit 1 ;;
    esac
elif [ -n "$VHOST_SRC" ]; then
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
IDENTITY_ASSERTED=no
if [ "$IDENTITY_SOURCE" != none ]; then
    echo "  identity: $IDENTITY_SOURCE"
    identity_run; IDENTITY_RC=$?
    case "$IDENTITY_RC" in
        0) IDENTITY_ASSERTED=yes ;;
        1) echo "  IDENTITY CHECK FAILED — this host may be serving another app"
           OK=1 ;;
        *) echo "  IDENTITY CHECK COULD NOT RUN (exit $IDENTITY_RC) — nothing was asserted about what this host serves"
           echo "  This is a tooling failure, NOT evidence of a misroute. Do not roll back on this alone."
           OK=1 ;;
    esac
# An ABSENT check used to be skipped in total silence, which is the same defect as a check that cannot tell
# "passed" from "never ran" — one layer up. A project published for weeks with no assertion at all that its
# hostname served its own application, and nothing ever said so. Say it, and say it where the result would
# have been, so the gap appears exactly where the evidence should.
elif [ "$GATE_PRESENT" = yes ] || [ -n "$VHOST_DIR" ] || [ -n "$PROXY_STACK" ]; then
    echo "  IDENTITY NOT CHECKED — no IDENTITY_CHECK is configured, and this box is SHARED."
    echo "  A shared proxy is exactly the condition where a 200 stops proving the response is yours: a name"
    echo "  collision can route this hostname at a neighbour's app, which answers 200 just as healthily. One"
    echo "  storefront served the wrong application for 41 hours with every other check green."
    echo "  Set IDENTITY_CHECK in config/publish.env — see the publish skill for the portable form."
else
    echo "  identity: not configured (no shared-proxy signals on this box)"
fi

# Re-read the counter: a container that crash-looped during verification climbs here even if a request slipped
# through between restarts.
RESTARTS_AFTER="$($SSH "docker inspect $APP_CONTAINER --format '{{.RestartCount}}'" 2>/dev/null)"
[ "$RESTARTS_AFTER" != "$RESTARTS" ] && { echo "  restarts climbed $RESTARTS -> $RESTARTS_AFTER"; OK=1; }
[ "$STATUS" = "running" ] || OK=1

if [ "$OK" = 0 ]; then
    # Qualify the headline rather than printing a bare OK. "PUBLISH OK" is read as "everything above was
    # checked", so on a shared box it would quietly certify the one property nobody verified.
    if [ "$IDENTITY_ASSERTED" = yes ]; then
        echo "PUBLISH OK  ($SSH_HOST, ${LOCAL:0:8})"
    else
        echo "PUBLISH OK — NOT IDENTITY-VERIFIED  ($SSH_HOST, ${LOCAL:0:8})"
        echo "  The pages answered 200, which proves something is serving them, not that it is yours."
    fi
else
    echo "PUBLISH FAILED — the stack is up but is not serving correctly."
    echo "  logs: ssh $SSH_HOST 'cd $COMPOSE_DIR && docker compose logs --tail 80 $APP_CONTAINER'"
    exit 1
fi
