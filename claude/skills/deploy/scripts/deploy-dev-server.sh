#!/bin/bash
# Restart a local long-running dev server (e.g. `npm run dev`) so `! deploy` brings the app
# up locally — the run-it-for-me counterpart to the install/publish deploy targets. Use for
# web apps you develop and run locally (Next.js, Remix, SvelteKit, Vite SPA, a plain Node
# server, ...) where "deploy" means "make the latest code runnable on this machine."
#
# Reads config/deploy.env (written by the deploy skill):
#   DEPLOY_TYPE=dev-server
#   DEV_DIR=<subdir holding the package.json with the dev script, relative to repo root; default .>   e.g. web
#   DEV_PORT=<port the server listens on; default 3000>
#   DEV_CMD=<command that starts the server; default 'npm run dev'>
#   DEV_PRESTART_CMD=<optional command run from the repo root between stopping the old server and
#                     starting the new one; empty means no pre-start step>
#
# Stops whatever holds the port, runs DEV_PRESTART_CMD if one is configured, then relaunches DEV_CMD
# detached so the server outlives this command and the Claude session. Logs go to
# <DEV_DIR>/dev-server.log (errors: .err.log).
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
DEV_PORT="$(getval DEV_PORT)"; DEV_PORT="${DEV_PORT:-3000}"
DEV_CMD="$(getval DEV_CMD)";  DEV_CMD="${DEV_CMD:-npm run dev}"
DEV_PRESTART_CMD="$(getval DEV_PRESTART_CMD)"

RUN_DIR="$REPO_DIR/$DEV_DIR"
LOG="$RUN_DIR/dev-server.log"
ERR="$RUN_DIR/dev-server.err.log"

if [ ! -d "$RUN_DIR" ]; then echo "ERROR: DEV_DIR '$DEV_DIR' not found under $REPO_DIR"; exit 1; fi

# PIDs listening on the port (cross-platform).
listening_pids() {
    if [ "$OS" = "win" ]; then
        MSYS_NO_PATHCONV=1 netstat -ano | grep -E "TCP.*[:.]${DEV_PORT}[[:space:]].*LISTENING" | awk '{print $NF}' | sort -u
    else
        lsof -nP -iTCP:"$DEV_PORT" -sTCP:LISTEN -t 2>/dev/null | sort -u
    fi
}

echo "Restarting dev server  (cmd: $DEV_CMD  dir: $DEV_DIR  port: $DEV_PORT)"

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
    echo "  nothing listening on port $DEV_PORT"
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
        # Last line, and only on success: the address is the point of the whole command, and a port number
        # alone is not it — someone still has to assemble the URL before they can look at the thing. Printed
        # by the script rather than left to whoever reports the run, so it cannot be omitted.
        echo "  open: http://localhost:$DEV_PORT"
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
