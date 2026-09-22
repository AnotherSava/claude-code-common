"""Pick a session running on the Windows machine and open it in the `remote` workspace.

Bound to a chord in agterm's keymap, which runs its command line detached with no terminal. That
suits this script exactly: the picker is agterm's own UI and the session is created through
agtermctl, so nothing here needs a TTY. The session agterm creates does have one, which is where the
attach actually runs.

The list is the far side's `cc-*` tmux sessions, because those are the ones that can actually be
attached. A Claude started in an ordinary Windows terminal owns its own pty: tmux cannot adopt a pty
it did not create, and `claude attach` covers only `claude --bg` sessions and serves one viewer — so
such a session is not merely awkward to join, it is unreachable, and listing it would offer
something that cannot be done.

The Claude Code Dashboard's roster supplies each row's status and current task. It is decoration
only: when it is unreachable the rows still list, without status. It cannot be the source, because
it reports every session on that machine whether or not anything can attach to it.

Starting something new is a second picker rather than a plain text box, listing the directories two
levels below the projects root so a name can be completed instead of remembered. It stays a second
step because folding two hundred folders into the first list would bury the handful of running
sessions the chord exists for. A directory the scan did not reach is still reachable by typing it.

Invoked through pick-session.sh, which loads the shared config and exports it.

Because the keymap detaches this, stderr goes nowhere a person will look, so every failure is also
posted as a desktop notification. Otherwise the chord does nothing and says nothing.
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

WORKSPACE = "remote"
BADGE = "⇄"
SESSION_PREFIX = "cc-"
DEFAULT_DASHBOARD = "http://127.0.0.1:9077"
SUBTITLE_LIMIT = 70
# Marks the row that opens the folder browser. Guarded against collision with a real directory
# before it is trusted, since nothing stops someone naming one this.
START_SENTINEL = "\u2026start-a-project"


def notify(body: str) -> None:
    subprocess.run(["agtermctl", "notify", body, "--title", "Remote session"], capture_output=True)


def fail(message: str) -> int:
    sys.stderr.write(f"pick-session: {message}\n")
    notify(message)
    return 1


def agtermctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["agtermctl", *args], capture_output=True, text=True)


# A folder is offered when it holds a `.claude` directory, which Claude Code creates the first time
# it runs somewhere. That is the closest available statement of "a place Claude is actually used",
# and it beats the alternatives on this tree: measured across 153 folders, `.claude` marked 23,
# `.git` 29 and a `CLAUDE.md` 14. The eight `.git` folders without `.claude` were mostly third-party
# clones nobody starts a session in, while `.claude` also caught two working folders that are not
# repositories at all and `.git` would have missed.
#
# Its failure mode is a project Claude has never run in, which has no marker to find yet — and that
# is exactly the case typing a path covers.
#
# Two levels reaches both `scheduler` and `bga/assistant`, which is where work actually starts, and
# is the same shape a session name encodes. The find goes one deeper because it looks for the marker
# rather than the folder holding it.
COMPLETION_DEPTH = 2
PRUNED = (".git", "node_modules", "dist", "build", "target", "__pycache__", ".venv", ".svelte-kit", ".next")


def inventory(config: "dict[str, str]") -> "tuple[list[str], list[str]]":
    """The far side's attachable sessions, and the directories worth completing against.

    Both in one round trip. Each costs about the same as the other and neither is slow, so fetching
    the directory list up front keeps the second picker instant without the first one waiting on a
    call it does not use.

    Asking tmux for each session's directory rather than unpicking its name: the name folds the
    path's separators into dashes, and a project legitimately called `travel-map` makes that fold
    impossible to invert.
    """
    prunes = " -o ".join(f"-name {name}" for name in PRUNED)
    # Wrapped in `sh -c "…"`, because the Windows sshd hands this to cmd.exe: there `'` is an
    # ordinary character rather than a quote, so the format string would split on its space, and
    # `|`, `(` and `)` are metacharacters. The double quotes are what cmd does honour, and sh
    # inside reads the rest.
    script = (
        "tmux list-sessions -F '#{session_name}|#{session_path}' 2>/dev/null; echo ---; "
        f"cd {config['WSL_PROJECT_ROOT']} && "
        f"find . -mindepth 2 -maxdepth {COMPLETION_DEPTH + 1} -type d \\( {prunes} \\) -prune "
        "-o -type d -name .claude -print"
    )
    remote = f'wsl -d {config["WSL_DISTRO"]} -- sh -c "{script}"'
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", f"{config['REMOTE_USER']}@{config['REMOTE_HOST']}", remote],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "ssh failed"
        raise RuntimeError(f"cannot reach {config['REMOTE_HOST']}: {message}")

    lines = result.stdout.replace("\r", "").splitlines()
    split = lines.index("---")

    root = config["WSL_PROJECT_ROOT"].rstrip("/") + "/"
    attachable = []
    for line in lines[:split]:
        name, _, path = line.partition("|")
        if not name.startswith(SESSION_PREFIX):
            continue
        attachable.append(path[len(root):] if path.startswith(root) else path.rsplit("/", 1)[-1])

    # The find reports each marker; the project is the folder holding it.
    markers = (line[2:] for line in lines[split + 1:] if line.startswith("./"))
    directories = sorted({marker.rsplit("/", 1)[0] for marker in markers if "/" in marker})
    return attachable, directories


def roster_status(device: str) -> "dict[str, str]":
    """Status and task per project, keyed by the project path's last component.

    Keyed loosely on purpose. The dashboard derives its own project id from the working directory
    and does not always keep the whole path below the projects root, so an exact match would drop
    the status off rows that have one. Getting it wrong costs a subtitle, never a row.
    """
    url = os.environ.get("TAURI_DASHBOARD_URL", DEFAULT_DASHBOARD).rstrip("/") + "/api/agents"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.load(response)
    except (urllib.error.URLError, OSError, ValueError):
        return {}

    status = {}
    for agent in data.get("agents", []):
        if agent.get("device") != device or agent.get("local"):
            continue
        label = (agent.get("label") or "").strip().replace("\n", " ")
        line = f"{agent.get('status', '?')} · {age(agent.get('status_age_ms'))}"
        status[agent["project"].rsplit("/", 1)[-1]] = f"{line} · {label}" if label else line
    return status


def age(milliseconds: "int | None") -> str:
    if milliseconds is None:
        return ""
    seconds = milliseconds // 1000
    if seconds < 90:
        return f"{seconds}s"
    if seconds < 5400:
        return f"{seconds // 60}m"
    if seconds < 172800:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def pick(rows: "list[dict]", prompt: str) -> "str | None":
    # --allow-custom is what makes a directory the scan did not reach still reachable: it is not in
    # the list, and typing it returns as a custom result.
    result = subprocess.run(
        ["agtermctl", "pick", "open", "--prompt", prompt, "--allow-custom"],
        input=json.dumps(rows) if rows else "",
        capture_output=True,
        text=True,
    )
    if result.returncode == 2:
        return None
    if result.returncode != 0:
        raise RuntimeError(f"picker failed: {result.stderr.strip() or 'unknown error'}")
    answer = json.loads(result.stdout)
    if answer.get("result") == "custom":
        return (answer.get("query") or "").strip() or None
    return answer.get("id")


def choose(attachable: "list[str]", directories: "list[str]", status: "dict[str, str]") -> "str | None":
    """The running sessions first; the directory tree only once you ask to start something.

    Two pickers rather than one list, because the two answer different questions. Folding the
    directories in would bury a handful of running sessions under two hundred places one could be
    started, and the running ones are what the chord is for.
    """
    rows = [
        {
            "id": project,
            "label": project,
            "subtitle": status.get(project.rsplit("/", 1)[-1], "running")[:SUBTITLE_LIMIT],
        }
        for project in attachable
    ]

    if rows:
        if directories:
            rows.append({"id": START_SENTINEL, "label": "Start a project…", "subtitle": "browse the folders"})
        chosen = pick(rows, "Windows session")
        if chosen != START_SENTINEL:
            return chosen

    running = set(attachable)
    browse = [
        {"id": directory, "label": directory, "subtitle": "not started"}
        for directory in directories
        if directory not in running
    ]
    return pick(browse, "Project to start")


def existing_tab(project: str) -> "str | None":
    """The id of a tab already attached to this project, if there is one.

    Opening a second local client on the same tmux session is not an error, but it is never what was
    wanted: both draw the same thing, and the pane is then clamped to the narrower of them.
    """
    result = agtermctl("tree", "--json")
    if result.returncode != 0:
        return None
    tree = json.loads(result.stdout)["result"]["tree"]
    for workspace in tree.get("workspaces", []):
        for session in workspace.get("sessions", []):
            foreground = session.get("foreground") or []
            if any(argument.endswith("attach.sh") for argument in foreground) and project in foreground:
                return session.get("id")
    return None


def main() -> int:
    try:
        config = {
            key: os.environ[key]
            for key in ("REMOTE_HOST", "REMOTE_USER", "REMOTE_DEVICE", "WSL_DISTRO", "WSL_PROJECT_ROOT")
        }
    except KeyError as missing:
        return fail(f"{missing.args[0]} is not set - run this through pick-session.sh")

    attach = os.path.join(os.path.dirname(os.path.abspath(__file__)), "attach.sh")

    try:
        attachable, directories = inventory(config)
        if START_SENTINEL in directories:
            directories = [d for d in directories if d != START_SENTINEL]
        project = choose(attachable, directories, roster_status(config["REMOTE_DEVICE"]))
    except (RuntimeError, ValueError, KeyError) as error:
        return fail(str(error))

    if project is None:
        return 0

    already = existing_tab(project)
    if already:
        agtermctl("session", "select", already)
        return 0

    result = agtermctl(
        "session", "new",
        "--workspace-name", WORKSPACE, "--create-workspace",
        "--name", f"{BADGE} {project}",
        "--command", f"{attach} {project}",
        "--wait",
    )
    if result.returncode != 0:
        return fail(f"could not open a session for {project}: {result.stderr.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
