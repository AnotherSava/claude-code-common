#!/bin/bash
# Restart a local long-running dev server (e.g. `npm run dev`) so `! deploy` brings the app
# up locally — the run-it-for-me counterpart to the install/publish deploy targets. Use for
# web apps you develop and run locally (Next.js, Remix, SvelteKit, Vite SPA, a plain Node
# server, ...) where "deploy" means "make the latest code runnable on this machine."
#
# Reads config/deploy.env (written by the deploy skill):
#   DEPLOY_TYPE=dev-server
#   DEV_DIR=<subdir holding the package.json with the dev script, relative to repo root; default .>   e.g. web
#   DEV_CMD=<command that starts the server; default 'npm run dev'>
#   DEV_PRESTART_CMD=<optional command run from the repo root between stopping the old server and
#                     starting the new one; empty means no pre-start step>
#   DEV_TAILNET=<no for a project whose origin is pinned to localhost (an API key, an OAuth redirect,
#                a CORS allowlist); anything else publishes the server on the tailnet>
#
# Stops whatever holds the port, runs DEV_PRESTART_CMD if one is configured, then relaunches DEV_CMD
# detached so the server outlives this command and the Claude session. Logs go to
# <DEV_DIR>/dev-server.log (errors: .err.log).
#
# Both ports come from the ports registry, asked on every run and recorded there: the one the server binds
# (`<repo>-dev-server`) and the one the tailnet URL is served on (`<repo>-dev-tailnet`). They cannot be the
# same number — a `tailscale serve` mapping holds the wildcard address, so one on the server's own port
# stops it rebinding at the next restart. Nothing in config/deploy.env names either.
set -uo pipefail

case "$(uname -s)" in
    Darwin) OS=mac ;;
    MINGW*|MSYS*|CYGWIN*) OS=win ;;
    *) OS=linux ;;
esac

# Resolve the repo root that holds config/deploy.env, so this works from any subdir — not only the repo root.
source "$(dirname "${BASH_SOURCE[0]}")/_repo-dir.sh"
REPO_DIR="$(resolve_repo_dir)"
DEPLOY_ENV="$REPO_DIR/config/deploy.env"
getval() { [ -f "$DEPLOY_ENV" ] && grep "^$1=" "$DEPLOY_ENV" | head -1 | cut -d= -f2- || true; }

DEV_DIR="$(getval DEV_DIR)";  DEV_DIR="${DEV_DIR:-.}"
DEV_CMD="$(getval DEV_CMD)";  DEV_CMD="${DEV_CMD:-npm run dev}"
DEV_PRESTART_CMD="$(getval DEV_PRESTART_CMD)"
DEV_TAILNET="$(getval DEV_TAILNET)"

RUN_DIR="$REPO_DIR/$DEV_DIR"
LOG="$RUN_DIR/dev-server.log"
ERR="$RUN_DIR/dev-server.err.log"
REPO_NAME="$(basename "$REPO_DIR")"
PY=python3; [ "$OS" = "win" ] && PY=python
SKILLS="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORTS="$SKILLS/ports/scripts/ports.py"

if [ ! -d "$RUN_DIR" ]; then echo "ERROR: DEV_DIR '$DEV_DIR' not found under $REPO_DIR"; exit 1; fi

# The port comes from the ports registry, keyed by use case, and no longer from config/deploy.env. One
# number in one place is what lets a project's own dev script stop carrying a copy — and what retired the
# old guess-from-package.json-else-3000 default, whose fallback was printlab's dev port. A
# DEV_PORT line left in deploy.env is ignored; `ports.py check --repo` reports it so it can be removed.
if ! DEV_PORT="$("$PY" "$PORTS" allocate --use-case "$REPO_NAME-dev-server" --owner "$REPO_NAME" \
        --notes "$REPO_NAME's local dev server, started by deploy-dev-server.sh as: $DEV_CMD")"; then
    echo "ERROR: the ports registry would not give $REPO_NAME a dev port (reason above), so nothing was started."
    echo "       Look it up with: $PY $PORTS list"
    exit 1
fi

# PIDs listening on the port. Both platforms' listings live in shared/port_probe.py, which also knows the
# holder neither listing shows: a `tailscale serve` mapping's listener is in a root-owned system extension,
# so an unprivileged lsof prints nothing about a port that cannot be bound.
listening_pids() { "$PY" "$SKILLS/shared/port_probe.py" pids "$DEV_PORT"; }

echo "Restarting dev server  (cmd: $DEV_CMD  dir: $DEV_DIR  port: $DEV_PORT)"

# 0. Clear a tailnet mapping on DEV_PORT itself. One of these holds the wildcard address, so the server
#    cannot rebind its own port and every process listing reports the port free — the state an earlier
#    `deploy` left behind when it fronted the server from the number the server binds. The front port is
#    a separate number now (step 5), so a mapping here is always stale.
if FRONTED="$("$PY" "$SKILLS/shared/port_probe.py" served "$DEV_PORT" 2>/dev/null)"; then
    echo "  clearing the tailnet mapping on port $DEV_PORT (fronts $FRONTED, and holds the wildcard address)"
    "$PY" "$SKILLS/shared/tailnet_publish.py" unpublish-port "$DEV_PORT" >/dev/null \
        || echo "  !! could not clear it — the server will fail to bind with nothing in any process listing"
fi

# 1. Stop whatever holds the port (tree kill — dev servers spawn worker children).
pids="$(listening_pids)"
if [ -n "$pids" ]; then
    for pid in $pids; do
        echo "  stopping PID $pid"
        if [ "$OS" = "win" ]; then
            MSYS_NO_PATHCONV=1 taskkill /PID "$pid" /T /F >/dev/null 2>&1 || true
        else
            pkill -TERM -P "$pid" 2>/dev/null || true
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    sleep 1
else
    # No visible PID is not the same as a free port. A root-owned or another user's listener appears in no
    # unprivileged listing, so the honest line comes from the probe that also tries the bind — otherwise
    # this says "nothing listening" about a port the server is about to fail on.
    "$PY" "$SKILLS/shared/port_probe.py" verdict "$DEV_PORT" | sed 's/^/  /'
fi

# 2. Run the project's pre-start step, if it has one — seeding a database, fetching a fixture, rendering a
#    generated file. It runs HERE, with the old server already stopped and the new one not yet launched, so
#    it can replace state the running app would otherwise be holding open or reading mid-request.
#
#    Run from the repo root rather than DEV_DIR, so the configured value is one repo-relative path on every
#    machine, and through `eval` so a value can carry pipes, flags and `&&` the way it would when typed.
#
#    A failure here does NOT stop the launch. `deploy` exists to leave the app runnable on this machine, and
#    the pre-start step is usually the part that needs something beyond it — a VPN, a remote host, a
#    credential. Losing the dev server because a laptop is offline is the worse outcome. So the failure is
#    reported where it happens AND again beside the URL at the end, where it cannot be scrolled past.
PRESTART_RC=0
if [ -n "$DEV_PRESTART_CMD" ]; then
    echo "Pre-start: $DEV_PRESTART_CMD"
    ( cd "$REPO_DIR" && eval "$DEV_PRESTART_CMD" )
    PRESTART_RC=$?
    if [ "$PRESTART_RC" -ne 0 ]; then
        echo "  !! PRE-START FAILED (exit $PRESTART_RC) — starting the server anyway, on whatever state it left behind"
    fi
fi

# 3. Launch detached so this command returns and the server outlives the session.
#
#    PORT carries the registry's number into the command. Next and Vite both read it, and Next classifies
#    an env-supplied port as source `env` rather than `default`, which keeps its retry-on-collision path
#    off — so the server binds this number or exits, instead of drifting to the next free one and leaving
#    the wait below polling a port nothing will ever open. A dev script that resolves the port itself
#    (`node scripts/dev.mjs`) asks the same registry for the same use case and arrives at the same answer.
export PORT="$DEV_PORT"
if [ "$OS" = "win" ]; then
    RUN_WIN="$(cygpath -w "$RUN_DIR")"; OUT_WIN="$(cygpath -w "$LOG")"; ERR_WIN="$(cygpath -w "$ERR")"
    powershell.exe -NoProfile -Command "Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' -ArgumentList '/c','$DEV_CMD' -WorkingDirectory '$RUN_WIN' -RedirectStandardOutput '$OUT_WIN' -RedirectStandardError '$ERR_WIN'" >/dev/null
else
    ( cd "$RUN_DIR" && nohup $DEV_CMD >"$LOG" 2>"$ERR" & )
fi

# 4. Wait for the port to come up.
printf "  waiting for port %s " "$DEV_PORT"
for _ in $(seq 1 40); do
    if [ -n "$(listening_pids)" ]; then
        printf " ready\n"
        echo "  logs: $DEV_DIR/dev-server.log (errors: $DEV_DIR/dev-server.err.log)"
        # Repeated here because the pre-start output is dozens of lines back by now, and a server that came
        # up perfectly reads as a clean run. Restated where the eye already lands.
        [ "$PRESTART_RC" -ne 0 ] && echo "  !! pre-start step FAILED earlier (exit $PRESTART_RC) — this server is running on unsynced state"
        # 5. Last line, and only on success: the address is the point of the whole command, and a port number
        #    alone is not it — someone still has to assemble the URL before they can look at the thing.
        #    Printed by the script rather than left to whoever reports the run, so it cannot be omitted. It
        #    is the tailnet address, so the link opens on every machine the user has. A project pinned to a
        #    localhost origin keeps localhost, because the tailnet name would fail its key or redirect check.
        #
        #    The tailnet port is NOT DEV_PORT. A `tailscale serve` mapping holds the wildcard address, so
        #    fronting the server from its own number stops it rebinding at the next restart — with every
        #    process listing showing the port free. The ports registry hands out the second number and
        #    records who owns it; asking it on every run is what makes the answer stable across deploys.
        if [ "$DEV_TAILNET" = "no" ]; then
            echo "  open: http://localhost:$DEV_PORT  (this machine only: DEV_TAILNET=no)"
        elif ! FRONT="$("$PY" "$PORTS" allocate \
                --use-case "$REPO_NAME-dev-tailnet" --owner "$REPO_NAME" --front-for "$DEV_PORT" \
                --notes "Tailnet front port for $REPO_NAME's dev server on $DEV_PORT. Allocated by deploy-dev-server.sh; the origin cannot share its own number.")"; then
            echo "  open: http://localhost:$DEV_PORT  (this machine only: no tailnet port allocated, reason above)"
        elif URL="$("$PY" "$SKILLS/shared/tailnet_publish.py" publish-port "$FRONT" --target "$DEV_PORT")"; then
            echo "  open: $URL"
        else
            echo "  open: http://localhost:$DEV_PORT  (this machine only: not published, reason above)"
        fi
        exit 0
    fi
    printf "."; sleep 1
done
printf " timed out\n"
echo "  server did not come up — check $DEV_DIR/dev-server.err.log"
# Named as a candidate cause rather than a footnote: a pre-start step that half-finished is exactly the thing
# that leaves a server unable to boot, and the error log will describe the symptom, not this.
[ "$PRESTART_RC" -ne 0 ] && echo "  the pre-start step also FAILED (exit $PRESTART_RC) — check that before the log"
exit 1
