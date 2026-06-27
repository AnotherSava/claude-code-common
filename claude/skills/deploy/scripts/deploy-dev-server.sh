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
#
# Stops whatever holds the port, then relaunches DEV_CMD detached so the server outlives this
# command and the Claude session. Logs go to <DEV_DIR>/dev-server.log (errors: .err.log).
set -uo pipefail

case "$(uname -s)" in
    Darwin) OS=mac ;;
    MINGW*|MSYS*|CYGWIN*) OS=win ;;
    *) OS=linux ;;
esac

REPO_DIR="$(pwd)"
DEPLOY_ENV="$REPO_DIR/config/deploy.env"
getval() { [ -f "$DEPLOY_ENV" ] && grep "^$1=" "$DEPLOY_ENV" | head -1 | cut -d= -f2- || true; }

DEV_DIR="$(getval DEV_DIR)";  DEV_DIR="${DEV_DIR:-.}"
DEV_PORT="$(getval DEV_PORT)"; DEV_PORT="${DEV_PORT:-3000}"
DEV_CMD="$(getval DEV_CMD)";  DEV_CMD="${DEV_CMD:-npm run dev}"

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

# 2. Launch detached so this command returns and the server outlives the session.
if [ "$OS" = "win" ]; then
    RUN_WIN="$(cygpath -w "$RUN_DIR")"; OUT_WIN="$(cygpath -w "$LOG")"; ERR_WIN="$(cygpath -w "$ERR")"
    powershell.exe -NoProfile -Command "Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' -ArgumentList '/c','$DEV_CMD' -WorkingDirectory '$RUN_WIN' -RedirectStandardOutput '$OUT_WIN' -RedirectStandardError '$ERR_WIN'" >/dev/null
else
    ( cd "$RUN_DIR" && nohup $DEV_CMD >"$LOG" 2>"$ERR" & )
fi

# 3. Wait for the port to come up.
printf "  waiting for port %s " "$DEV_PORT"
for _ in $(seq 1 40); do
    if [ -n "$(listening_pids)" ]; then
        printf " ready\n"
        echo "  logs: $DEV_DIR/dev-server.log (errors: $DEV_DIR/dev-server.err.log)"
        exit 0
    fi
    printf "."; sleep 1
done
printf " timed out\n"
echo "  server did not come up — check $DEV_DIR/dev-server.err.log"
exit 1
