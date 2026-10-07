#!/usr/bin/env python3
"""A dev-server deploy returns its caller's output stream when it exits.

`deploy-dev-server.sh` launches the server detached, so the server outlives the script. If the
server inherits the stream the caller is reading the script's output from, the caller never sees
end-of-file: `bash scripts/deploy.sh | tail` and every tool that captures output until EOF wait for
as long as the server runs. The script itself has long since exited 0 by then, so nothing reports a
failure — the run just never finishes, and whatever it was going to print, the tailnet URL included,
is never shown.

Measured 2026-10-06 on Windows: `Start-Process` with its streams redirected creates the child with
handle inheritance on, and the server chain (`cmd.exe -> doppler -> node`) held PowerShell's stderr,
which was the pipe to `tail`. The run sat until the tool timeout killed it; a plain run through a
tool that waits only for the process to exit returned in 13 s and hid it.

What is asserted, with a stand-in server on a port from a scratch registry and the tailnet off:

  returns     the caller reading stdout reaches EOF soon after the script exits
  succeeds    the script exits 0 and prints the address it brought up
  detached    the server is still listening afterwards — closing the stream must not cost that

Usage:  python claude/tests/deploy-dev-server.py
Exit:   0 all hold, 1 one does not or the run could not be set up
"""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SCRIPT = os.path.join(REPO, "claude", "skills", "deploy", "scripts", "deploy-dev-server.sh")
PORT_PROBE = os.path.join(REPO, "claude", "skills", "shared", "port_probe.py")
WINDOWS = sys.platform == "win32"
PY = "python" if WINDOWS else "python3"

# How long after the script exits the reader may still be waiting. The script's own wait for the port
# is bounded at 40 s, so a healthy run is well inside this; a held stream never ends at all.
EOF_GRACE = 15
RUN_LIMIT = 90

SERVER = """import os, socket, time
s = socket.socket()
s.bind(("127.0.0.1", int(os.environ["PORT"])))
s.listen()
while True:
    time.sleep(3600)
"""

FAILURES = []


def fail(message: str) -> None:
    FAILURES.append(message)


def listening(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(1)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def stop_server(port: int) -> None:
    """Kill the stand-in by the port it took, tree and all, so the held stream closes too."""
    pids = subprocess.run([sys.executable, PORT_PROBE, "pids", str(port)], capture_output=True, text=True).stdout.split()
    for pid in pids:
        if WINDOWS:
            subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True)
        else:
            subprocess.run(["pkill", "-KILL", "-P", pid], capture_output=True)
            subprocess.run(["kill", "-KILL", pid], capture_output=True)


def main() -> int:
    bash = shutil.which("bash")
    if not bash:
        print("deploy dev server: NOT RUN — no bash on PATH")
        return 1

    scratch = tempfile.mkdtemp(prefix="deploy-dev-server-test.")
    project = os.path.join(scratch, "deploy-pipe-test")
    os.makedirs(os.path.join(project, "config"))
    with open(os.path.join(project, "serve.py"), "w", encoding="utf-8") as handle:
        handle.write(SERVER)
    with open(os.path.join(project, "config", "deploy.env"), "w", encoding="utf-8") as handle:
        handle.write(f"DEPLOY_TYPE=dev-server\nDEV_DIR=.\nDEV_CMD={PY} serve.py\nDEV_TAILNET=no\n")
    registry = os.path.join(scratch, "registry.json")
    with open(registry, "w", encoding="utf-8") as handle:
        json.dump({"claims": []}, handle)

    env = dict(os.environ, CLAUDE_PORTS_REGISTRY=registry)
    proc = subprocess.Popen([bash, SCRIPT], cwd=project, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    chunks = []
    reader = threading.Thread(target=lambda: chunks.append(proc.stdout.read()), daemon=True)
    reader.start()

    port = None
    try:
        try:
            code = proc.wait(timeout=RUN_LIMIT)
        except subprocess.TimeoutExpired:
            proc.kill()
            fail(f"the script itself did not exit within {RUN_LIMIT} s")
            code = None
        reader.join(timeout=EOF_GRACE)
        held = reader.is_alive()

        # The registry is the record of which port the run took, and it is readable whether or not the
        # output ever arrived — which is what lets a held stream still be cleaned up.
        with open(registry, encoding="utf-8") as handle:
            claims = json.load(handle).get("claims", [])
        port = next((c.get("port") for c in claims if c.get("use_case") == "deploy-pipe-test-dev-server"), None)

        if held:
            fail(f"the script exited {code}, and {EOF_GRACE} s later its caller was still waiting for end of output: "
                 "the detached server holds the caller's stream, so `deploy | tail` and any tool reading to EOF hang")
        elif code == 0:
            output = (chunks[0] if chunks else b"").decode("utf-8", "replace")
            if not re.search(r"open: http://localhost:\d+", output):
                fail(f"exit 0 without the address line; output was:\n{output}")
        elif code is not None:
            output = (chunks[0] if chunks else b"").decode("utf-8", "replace")
            fail(f"the script exited {code}; output was:\n{output}")

        if port is None:
            fail("the scratch registry holds no dev-server claim, so the run never asked for a port")
        elif code == 0 and not listening(port):
            fail(f"the script exited 0 and nothing listens on {port} afterwards: the server did not outlive it")
    finally:
        if port is not None:
            stop_server(port)
        reader.join(timeout=10)
        time.sleep(1)
        shutil.rmtree(scratch, ignore_errors=True)

    if FAILURES:
        print(f"deploy dev server: {len(FAILURES)} failure(s)\n")
        for failure in FAILURES:
            print(f"  {failure}")
        print()
        return 1
    print("deploy dev server: returns its caller's stream, exits 0 with the address, server still up")
    return 0


if __name__ == "__main__":
    sys.exit(main())
