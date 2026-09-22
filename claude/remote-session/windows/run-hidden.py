"""Run a command with no console window, appending its output to a log.

    pythonw.exe run-hidden.py --log <file> -- <command> [args...]

Both halves are required and each looks sufficient on its own. Running under `pythonw` keeps the
launcher windowless but the child still allocates its own console; passing CREATE_NO_WINDOW keeps
the child quiet but the launcher already flashed. Either one alone puts a console on the user's
desktop.

Because `pythonw` discards stdout and stderr, the log is the only place a failure can surface — a
crash under it otherwise leaves no trace anywhere.
"""

import datetime
import os
import subprocess
import sys

# subprocess.CREATE_NO_WINDOW exists on Windows only; the fallback keeps the script importable and
# testable elsewhere.
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def stamp() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[0] != "--log" or "--" not in argv:
        sys.stderr.write("usage: run-hidden.py --log <file> -- <command> [args...]\n")
        return 2

    log_path = argv[1]
    command = argv[argv.index("--") + 1:]
    if not command:
        sys.stderr.write("run-hidden: no command after --\n")
        return 2

    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    with open(log_path, "a", encoding="utf-8", errors="replace") as log:
        log.write(f"=== {stamp()} starting: {command}\n")
        log.flush()
        try:
            completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, creationflags=CREATE_NO_WINDOW)
        except OSError as error:
            log.write(f"=== {stamp()} failed to start: {error}\n")
            return 1
        log.write(f"=== {stamp()} exited {completed.returncode}\n")
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
