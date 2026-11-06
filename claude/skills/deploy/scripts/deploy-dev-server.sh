#!/bin/bash
# Restart a local long-running dev server (e.g. `npm run dev`) so `! deploy` brings the app
# up locally — the run-it-for-me counterpart to the install/publish deploy targets. Use for
# web apps you develop and run locally (Next.js, Remix, SvelteKit, Vite SPA, a plain Node
# server, ...) where "deploy" means "make the latest code runnable on this machine."
#
# Reads config/deploy.env, committed, with config/deploy.local.env overriding it per machine (shared/deploy-config.sh):
#   DEPLOY_TYPE=dev-server
#   DEV_DIR=<subdir holding the package.json with the dev script, relative to repo root; default .>   e.g. web
#   DEV_CMD=<command that starts the server; default 'npm run dev'>
#   DEV_PRESTART_CMD=<optional command run from the repo root on every deploy, between stopping the old server
#                     and starting the new one; empty means no pre-start step>
#   DEV_DB_SYNC_CMD=<optional command run from the repo root only on `deploy --db`, in the same gap as
#                    DEV_PRESTART_CMD and before it: replacing the local data with production's. Empty means
#                    --db is refused, so a plain run never reaches production.>
#   DEV_TAILNET=<no for a project whose origin is pinned to localhost (an API key, an OAuth redirect,
#                a CORS allowlist); anything else publishes the server on the tailnet>
#
# Arguments: --db runs DEV_DB_SYNC_CMD. Nothing else is accepted.
#
# Stops whatever holds the port, runs the data sync and the pre-start step if either is set, then relaunches DEV_CMD
# detached so the server outlives this command and the Claude session. Logs go to
# <DEV_DIR>/dev-server.log (errors: .err.log). A successful start is also
# reported to the tauri-dashboard (TAURI_DASHBOARD_URL), best-effort and silent.
#
# Both ports come from the ports registry, asked on every run and recorded there under the use cases
# `ports.py dev-use-case` names: the one the server binds and the one the tailnet URL is served on. They cannot be the
# same number — a `tailscale serve` mapping holds the wildcard address, so one on the server's own port
# stops it rebinding at the next restart. Nothing in config/deploy.env names either.
set -uo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../../shared/deploy-config.sh"
REPO_DIR="$DEPLOY_REPO_DIR"
OS="$DEPLOY_OS"

DEV_DIR="$(deploy_get DEV_DIR)";  DEV_DIR="${DEV_DIR:-.}"
DEV_CMD="$(deploy_get DEV_CMD)";  DEV_CMD="${DEV_CMD:-npm run dev}"
DEV_PRESTART_CMD="$(deploy_get DEV_PRESTART_CMD)"
DEV_DB_SYNC_CMD="$(deploy_get DEV_DB_SYNC_CMD)"
DEV_TAILNET="$(deploy_get DEV_TAILNET)"

SYNC_DB=0
for arg in "$@"; do
    case "$arg" in
        --db) SYNC_DB=1 ;;
        *) echo "ERROR: unknown argument '$arg' — deploy takes only --db"; exit 1 ;;
    esac
done
if [ "$SYNC_DB" -eq 1 ] && [ -z "$DEV_DB_SYNC_CMD" ]; then
    echo "ERROR: --db asks for a data sync, and config/deploy.env names no DEV_DB_SYNC_CMD, so nothing was done."
    exit 1
fi

RUN_DIR="$REPO_DIR/$DEV_DIR"
LOG="$RUN_DIR/dev-server.log"
ERR="$RUN_DIR/dev-server.err.log"
REPO_NAME="$(basename "$REPO_DIR")"
PY="$DEPLOY_PY"
SKILLS="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORTS="$SKILLS/ports/scripts/ports.py"
# A claim's owner is the repo's GitHub name, which is the same on every clone; the use case still comes from the
# folder name, so renaming a clone's folder starts a new claim rather than moving the old one. ports.py derives
# both, for this script and for the `dev-port` command alike, so the two launchers hold one claim.
OWNER="$("$PY" "$PORTS" dev-use-case --from "$REPO_DIR" --owner)"
SERVER_USE_CASE="$("$PY" "$PORTS" dev-use-case --from "$REPO_DIR" --role server)"
TAILNET_USE_CASE="$("$PY" "$PORTS" dev-use-case --from "$REPO_DIR" --role tailnet)"

if [ ! -d "$RUN_DIR" ]; then echo "ERROR: DEV_DIR '$DEV_DIR' not found under $REPO_DIR"; exit 1; fi

# The port comes from the ports registry, keyed by use case, and no longer from config/deploy.env. One
# number in one place is what lets a project's own dev script stop carrying a copy — and what retired the
# old guess-from-package.json-else-3000 default, whose fallback was printlab's dev port. A
# DEV_PORT line left in deploy.env is ignored; `ports.py check --repo` reports it so it can be removed.
if ! DEV_PORT="$("$PY" "$PORTS" allocate --use-case "$SERVER_USE_CASE" --owner "$OWNER" \
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

# 2. Run the --db data sync and the project's pre-start step, if either is set — the pre-start step fetching a
#    fixture or rendering a generated file. They run HERE, with the old server already stopped and the new one
#    not yet launched, so they can replace state the running app would otherwise be holding open or reading
#    mid-request.
#
#    Run from the repo root rather than DEV_DIR, so the configured value is one repo-relative path on every
#    machine, and through `eval` so a value can carry pipes, flags and `&&` the way it would when typed.
#
#    A failure here does NOT stop the launch. `deploy` exists to leave the app runnable on this machine, and
#    these steps are usually the part that needs something beyond it — a VPN, a remote host, a credential.
#    Losing the dev server because a laptop is offline is the worse outcome. So the failure is reported where
#    it happens AND again beside the URL at the end, where it cannot be scrolled past.
#
#    The --db data sync runs first, in the same gap: replacing a database the running app holds open is the
#    case this gap exists for. The pre-start step still runs after a failed sync, since it does not depend on it.
STEP_FAILED=""
if [ "$SYNC_DB" -eq 1 ]; then
    echo "Data sync: $DEV_DB_SYNC_CMD"
    ( cd "$REPO_DIR" && eval "$DEV_DB_SYNC_CMD" )
    rc=$?
    if [ "$rc" -ne 0 ]; then
        STEP_FAILED="data sync (exit $rc)"
        echo "  !! DATA SYNC FAILED (exit $rc) — starting the server anyway, on the existing local data"
    fi
fi
if [ -n "$DEV_PRESTART_CMD" ]; then
    echo "Pre-start: $DEV_PRESTART_CMD"
    ( cd "$REPO_DIR" && eval "$DEV_PRESTART_CMD" )
    rc=$?
    if [ "$rc" -ne 0 ]; then
        STEP_FAILED="${STEP_FAILED:+$STEP_FAILED, }pre-start step (exit $rc)"
        echo "  !! PRE-START FAILED (exit $rc) — starting the server anyway, on whatever state it left behind"
    fi
fi

# 3. Launch detached so this command returns and the server outlives the session.
#
#    PORT carries the registry's number into the command. Next and Vite both read it, and Next classifies
#    an env-supplied port as source `env` rather than `default`, which keeps its retry-on-collision path
#    off — so the server binds this number or exits, instead of drifting to the next free one and leaving
#    the wait below polling a port nothing will ever open. A dev script that resolves the port itself
#    (`dev-port <command>`) asks the same registry for the same use case and arrives at the same answer.
#
#    None of this command's own streams may reach the server. It outlives the script, so a stream it holds
#    never closes, and whoever reads this script's output to EOF — `deploy | tail`, a tool capturing it —
#    waits for as long as the server runs. Start-Process with redirection creates the child with handle
#    inheritance on, passing it every stream PowerShell holds, so PowerShell gets none of the caller's: its
#    launch error goes to the server's error log instead, where the timeout message below already points.
#    claude/tests/deploy-dev-server.py reads the output through a pipe and fails on a held stream.
export PORT="$DEV_PORT"
if [ "$OS" = "win" ]; then
    RUN_WIN="$(cygpath -w "$RUN_DIR")"; OUT_WIN="$(cygpath -w "$LOG")"; ERR_WIN="$(cygpath -w "$ERR")"
    powershell.exe -NoProfile -Command "try { Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' -ArgumentList '/c','$DEV_CMD' -WorkingDirectory '$RUN_WIN' -RedirectStandardOutput '$OUT_WIN' -RedirectStandardError '$ERR_WIN' -ErrorAction Stop } catch { Set-Content -LiteralPath '$ERR_WIN' -Value ('launch failed: ' + \$_); exit 1 }" </dev/null >/dev/null 2>&1 \
        || echo "  !! the launch itself failed — the reason is in $DEV_DIR/dev-server.err.log"
else
    #    The trailing redirection is on the SUBSHELL, and it is the half that matters here: the inner
    #    redirections cover the server, but the forked subshell keeps this script's own stdout and
    #    stderr, and it outlives the script holding them. Measured on macOS 2026-10-06 — the server's
    #    descriptors were /dev/null, the two logs and its listen socket, while a surviving `bash` held
    #    the caller's pipe on fds 1 and 2, and EOF never arrived in 90 s. Same shape as the
    #    `</dev/null >/dev/null 2>&1` on the PowerShell call above.
    ( cd "$RUN_DIR" && nohup $DEV_CMD </dev/null >"$LOG" 2>"$ERR" & ) </dev/null >/dev/null 2>&1
fi

# 4. Wait for the port to come up.
printf "  waiting for port %s " "$DEV_PORT"
for _ in $(seq 1 40); do
    if [ -n "$(listening_pids)" ]; then
        printf " ready\n"
        echo "  logs: $DEV_DIR/dev-server.log (errors: $DEV_DIR/dev-server.err.log)"
        # Repeated here because the pre-start output is dozens of lines back by now, and a server that came
        # up perfectly reads as a clean run. Restated where the eye already lands.
        [ -n "$STEP_FAILED" ] && echo "  !! FAILED earlier: $STEP_FAILED — this server is running on whatever state that left"
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
        PUBLISHED_URL=
        if [ "$DEV_TAILNET" = "no" ]; then
            echo "  open: http://localhost:$DEV_PORT  (this machine only: DEV_TAILNET=no)"
        elif ! FRONT="$("$PY" "$PORTS" allocate \
                --use-case "$TAILNET_USE_CASE" --owner "$OWNER" --front-for "$DEV_PORT" \
                --notes "Tailnet front port for $REPO_NAME's dev server on $DEV_PORT. Allocated by deploy-dev-server.sh; the origin cannot share its own number.")"; then
            echo "  open: http://localhost:$DEV_PORT  (this machine only: no tailnet port allocated, reason above)"
        elif URL="$("$PY" "$SKILLS/shared/tailnet_publish.py" publish-port "$FRONT" --target "$DEV_PORT")"; then
            echo "  open: $URL"
            PUBLISHED_URL=$URL
        else
            echo "  open: http://localhost:$DEV_PORT  (this machine only: not published, reason above)"
        fi
        # Tell the tauri-dashboard about the server, so the agterm session it was started from shows it
        # running and can open it, and so does the other machine's ⇄ tab onto this session. That tab is
        # why it goes out with no agterm session too: a Windows agent runs under the WSL tmux holder and
        # has none, and the dashboard finds its row from the Claude Code session instead. The tailnet
        # URL is what the other machine opens it at. The dashboard forgets the server once the port
        # stops answering. It may not be running, so this is best-effort and silent: a server that came
        # up is the result, and its line is extra.
        "$PY" - "$SKILLS/shared" "$DEV_PORT" "$REPO_DIR" "${AGTERM_SESSION_ID:-}" "${CLAUDE_CODE_SESSION_ID:-}" "$PUBLISHED_URL" <<'EOF' >/dev/null 2>&1 || true
import sys
shared, port, repo_dir, session, claude_session, url = sys.argv[1:7]
sys.path.insert(0, shared)
from peer_relay import dashboard_open
dashboard_open("/api/dev-server", {"port": int(port), "dir": repo_dir, "session": session or None, "claude_session": claude_session or None, "url": url or None}, 2).read()
EOF
        exit 0
    fi
    printf "."; sleep 1
done
printf " timed out\n"
echo "  server did not come up — check $DEV_DIR/dev-server.err.log"
# Named as a candidate cause rather than a footnote: a step that half-finished is exactly the thing
# that leaves a server unable to boot, and the error log will describe the symptom, not this.
[ -n "$STEP_FAILED" ] && echo "  also FAILED earlier: $STEP_FAILED — check that before the log"
exit 1
