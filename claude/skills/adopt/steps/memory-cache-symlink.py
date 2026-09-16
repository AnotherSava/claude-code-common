#!/usr/bin/env python3
"""v4 — point this machine's memory cache for a repo at the repo's own .claude/memory/.

Claude Code writes project memory to a machine-local cache directory named after the
repo's path. Nothing version-controls it, so the knowledge is invisible from the other
machine and gone when the cache is cleared. The convention redirects that directory, by
a link, at a committed `.claude/memory/` inside the repo, and `scripts/link-project-memory.sh`
is what makes the link; this step is that script with the preconditions and the
assertions `/adopt` owes around it.

Three facts shape everything below.

**The cache directory's name is a mangle of the repo's path, so the spelling matters.**
Every non-alphanumeric character becomes one dash. Compute it from a different spelling
of the same directory and the link points somewhere the harness never reads, while every
check still passes. So the path comes from `git rev-parse --show-toplevel`, the same
producer the shell script uses, and a differently-cased sibling already sitting in the
cache is named rather than ignored — both `~/projects` and `~/Projects` open one
directory here, and the harness keys on whichever the session was started from.

**The link is asserted with `samefile`, never with a path string.** On Git Bash `ln -s`
silently makes a copy, and a copy resolves to itself, so `realpath` on it returns a
perfectly sensible path and `isdir` calls it healthy while it mirrors nothing. Different
inodes is the only signal (learnings/comparing-paths-symlinks-and-case.md). The same test
covers the Windows directory junction, which `os.path.islink` answers False for since
Python 3.8 — keying on that would report nine correctly wired repos as broken.

**A file in the un-versioned cache is copied and re-read before the original goes.**
Assert per item, never on a tally (learnings/git-stash-pull-safety.md).

    memory-cache-symlink.py probe  <repo-root>              0 applies · 1 no · 2 ask · 3 error
    memory-cache-symlink.py apply  <repo-root> [--dry-run]  0 done · 3 stopped, sources intact
    memory-cache-symlink.py verify <repo-root>              0 in shape · 2 unobservable · 3 not

The last line `apply` prints is the record note, and so is the last line `verify` prints on
a repo already in the target shape. Both are one line, carry no tab, and name no absolute
path: an `applied` machine step writes the committed record too, and that file travels to a
machine where this machine's paths mean nothing.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
from typing import NamedTuple

# sys.path[0] is already this directory when the engine runs the script by path; the insert
# is what lets the authoring gate import this module directly as well.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _dispatch  # noqa: E402  — path set above

REPO_MEM_REL = ".claude/memory"
# <repo>/claude/skills/adopt/steps/<this file> -> <repo>/claude/scripts/link-project-memory.sh.
# `realpath` first, because the steps directory is normally reached through the ~/.claude symlink
# and the script is a sibling of the checkout, not of the installed path.
CLAUDE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
LINK_SCRIPT = os.path.join(CLAUDE_DIR, "scripts", "link-project-memory.sh")
LINK_TIMEOUT = 60

# Every non-alphanumeric character becomes exactly one dash — `:` `/` `\` `.` `_` and a space
# each get their own. `D:\work\my-app` is `D--work-my-app` because `:` and `\` are two of them,
# not because a separator doubles (skills/skill/references/claude-project-memory-paths.md).
MANGLE_RE = re.compile(r"[^a-zA-Z0-9]")

# Emit UTF-8 whatever the console codepage is: this prints paths and memory filenames back
# verbatim, and one non-ASCII character through Windows' cp1252 default raises rather than
# prints, turning a healthy run into an exit 3.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class Root(NamedTuple):
    path: str  # git's spelling of the repository root, "" when git would not answer
    detail: str


class Cache(NamedTuple):
    ident: str    # the mangled project id, which is the cache directory's name
    project: str  # <config>/projects/<ident>
    memory: str   # <config>/projects/<ident>/memory — the path the harness reads
    projects: str  # <config>/projects


def config_dir() -> str:
    """This machine's Claude Code state directory.

    Resolved as `${CLAUDE_CONFIG_DIR:-$HOME/.claude}`, which is how `scripts/identity-check.py`,
    the publish script and the tune-output preflight already resolve it. A machine that relocates
    its config dir and a step that assumed `~/.claude` would disagree silently, and the link would
    sit in a directory the harness never opens — the one failure this step exists to catch.
    """
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def git_toplevel(root: str) -> Root:
    """The repository root as git spells it, or the reason git would not say.

    The shell script this step runs asks git the same question, so both sides come from one
    producer and cannot disagree about a symlinked or differently-cased path component
    (learnings/comparing-paths-symlinks-and-case.md). On Git Bash this answers a drive-letter path
    with forward slashes, which mangles the way the harness's own `pwd -W` does; a POSIX `pwd`
    there would not.
    """
    try:
        done = subprocess.run(["git", "-C", root, "rev-parse", "--show-toplevel"], capture_output=True,
                              encoding="utf-8", errors="replace", timeout=20)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return Root("", f"git could not be run ({exc})")
    if done.returncode != 0:
        return Root("", done.stderr.strip() or f"git rev-parse exited {done.returncode}")
    return Root(done.stdout.strip(), "") if done.stdout.strip() else Root("", "git named no repository root")


def cache_paths(repo_root: str) -> Cache:
    """Where the harness keeps this repo's memory on this machine."""
    projects = os.path.join(config_dir(), "projects")
    ident = MANGLE_RE.sub("-", repo_root)
    project = os.path.join(projects, ident)
    return Cache(ident, project, os.path.join(project, "memory"), projects)


def sibling_spellings(cache: Cache) -> list[str]:
    """Cache directories naming this same repo under a different spelling of its path.

    Both `~/projects` and `~/Projects` open one directory on a filesystem that folds case, and
    the harness keys its cache on the spelling the session was started from — so one repo can
    own two cache directories. Wiring the one the harness is not reading would leave the machine
    looking wired while every session still wrote outside the repo, so a variant is named.
    """
    # walk-unfiltered: everything this step lists is the machine-local Claude cache under the home
    # directory, outside every repo. There is no work tree to ask, and `check-ignore` there would
    # answer 128 or, worse, answer for whatever repo happens to be an ancestor.
    try:
        names = sorted(os.listdir(cache.projects))
    except OSError:
        return []
    return [name for name in names if name != cache.ident and name.casefold() == cache.ident.casefold()]


def is_link(path: str) -> bool:
    """Whether this entry is a link rather than a directory standing where one belongs.

    Used for wording only — the assertion is `samefile`. On Windows the link is a directory
    junction, which `os.path.islink` has answered False for since Python 3.8; `os.path.isjunction`
    arrived in 3.12, so it is reached through `getattr` rather than assumed present.
    """
    if os.path.islink(path):
        return True
    isjunction = getattr(os.path, "isjunction", None)
    return bool(isjunction and isjunction(path))


def describe(path: str) -> str:
    """What is actually sitting at a path, in the words a refusal needs."""
    if not os.path.lexists(path):
        return "nothing"
    if is_link(path):
        target = os.path.realpath(path)
        return f"a link to {target}" if os.path.exists(path) else f"a dangling link to {target}"
    if os.path.isdir(path):
        return "a plain directory"
    return "a file"


def cache_entries(path: str) -> list[str]:
    """Names sitting in the un-versioned cache directory, dotfiles included."""
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def digest(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def collisions(cache_mem: str, repo_mem: str) -> list[str]:
    """Names held by both the cache directory and the repo copy.

    Two files under one name are two versions of one memory, and which one survives is not a
    guess this step makes. Every other name in the cache is carried across by `apply`.
    """
    return [name for name in cache_entries(cache_mem) if os.path.lexists(os.path.join(repo_mem, name))]


def migrate(cache_mem: str, repo_mem: str) -> tuple[list[str], int]:
    """Carry each un-versioned file into the repo copy, re-read it, and only then remove it.

    One file at a time, and the source goes only after the destination has been read back and
    found byte-identical — zero copies means it was lost and a tally passes the moment one of
    each happens (learnings/git-stash-pull-safety.md). Mode "xb" so a name that appeared between
    the collision check and here stops this rather than being overwritten, and a byte copy rather
    than a text one so no line ending is rewritten on the way.
    """
    lines: list[str] = []
    for name in cache_entries(cache_mem):
        source, destination = os.path.join(cache_mem, name), os.path.join(repo_mem, name)
        if not os.path.isfile(source) or os.path.islink(source):
            lines.append(f"REFUSED     {name} is not a regular file, and this step moves only files")
            return lines, 3
        try:
            with open(source, "rb") as reader, open(destination, "xb") as writer:
                writer.write(reader.read())
            if digest(source) != digest(destination):
                lines.append(f"MISMATCHED  {name} was copied into {REPO_MEM_REL}/ and read back different")
                return lines, 3
            os.remove(source)
        except OSError as exc:
            lines.append(f"FAILED      {name} ({exc})")
            return lines, 3
        lines.append(f"moved       {name} -> {REPO_MEM_REL}/{name}")
    return lines, 0


def run_link_script(root: str) -> tuple[int, str]:
    """Make the link, through the one script that already knows how on both machines.

    Never `ln -s` from here: on Git Bash it makes a copy, leaving a machine that looks wired and
    is not. The script creates a directory junction through PowerShell there and a symlink
    everywhere else, which is why this step runs it rather than reimplementing it.
    """
    if not os.path.isfile(LINK_SCRIPT):
        return 3, f"the linking script is not at claude/scripts/link-project-memory.sh ({LINK_SCRIPT})"
    # Resolve the interpreter to an absolute path rather than passing the bare name: on Windows a bare
    # `bash` reaches System32's WSL launcher, not Git Bash, and the script then runs on an OS where no
    # path it is handed exists. Note `which` is the fix here only because its result is what gets
    # spawned — used as a *check* beside a bare-name spawn it reports Git Bash while WSL runs, which is
    # the trap in ~/.claude/learnings/windows-spawning-bash.md.
    bash = shutil.which("bash")
    if bash is None:
        return 3, "bash is not on PATH, so claude/scripts/link-project-memory.sh cannot be run"
    try:
        done = subprocess.run([bash, LINK_SCRIPT, root], capture_output=True, encoding="utf-8",
                              errors="replace", timeout=LINK_TIMEOUT)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return 3, f"link-project-memory.sh could not be run ({exc})"
    if done.returncode != 0:
        return 3, (done.stderr or done.stdout or "").strip() or f"link-project-memory.sh exited {done.returncode}"
    return 0, ""


def shape(root: str) -> tuple[int, str, Cache | None]:
    """The target shape, asserted once for every caller: is the cache this repo's own directory.

    Returns (0, note, cache) when it is, and otherwise a code with the sentence saying why not.
    Asserted with `samefile`, which compares st_dev/st_ino, so a copy standing where the link
    belongs fails it — while `realpath`, `isdir` and any string comparison all call that copy
    healthy. Same test covers the Windows junction, which is not an `os.path.islink`.
    """
    repo_mem = os.path.join(root, *REPO_MEM_REL.split("/"))
    if not os.path.isdir(repo_mem):
        return 2, (f"no {REPO_MEM_REL}/ in this repo, so this machine's cache has nothing to be pointed at; "
                   f"whether this repo keeps project memory at all is not a shape this script can read"), None
    top = git_toplevel(root)
    if not top.path:
        return 3, (f"git could not be asked which directory is this repository's root ({top.detail}), and the "
                   f"cache directory the harness reads is named after exactly that path"), None
    cache = cache_paths(top.path)
    if not os.path.lexists(cache.memory):
        variants = sibling_spellings(cache)
        extra = f"; the cache does hold {', '.join(variants)}, which is this same repo under another spelling of its path" if variants else ""
        return 3, f"this machine keeps no memory cache for this repo at {cache.memory}{extra}", cache
    try:
        same = os.path.samefile(cache.memory, repo_mem)
    except OSError as exc:
        return 3, f"{cache.memory} is {describe(cache.memory)} and could not be compared with {REPO_MEM_REL}/ ({exc})", cache
    if not same:
        return 3, (f"{cache.memory} is {describe(cache.memory)} rather than this repo's {REPO_MEM_REL}/ — "
                   f"the two are different directories, so memory written through the cache never reaches the repo"), cache
    kind = "a link" if is_link(cache.memory) else "the same directory"
    return 0, (f"this machine's memory cache for this repo is {kind} to {REPO_MEM_REL}/, asserted with samefile "
               f"rather than a path string, so a copy standing in for the link would have failed it"), cache


def cmd_probe(root: str) -> int:
    repo_mem = os.path.join(root, *REPO_MEM_REL.split("/"))
    if os.path.lexists(repo_mem) and not os.path.isdir(repo_mem):
        print(f"{REPO_MEM_REL} is {describe(repo_mem)} rather than a directory, so there is nothing this "
              f"machine's cache can be pointed at. Move it aside or make it the directory the convention "
              f"describes, then re-run.")
        return 2
    top = git_toplevel(root)
    if not top.path:
        print(f"git could not be asked which directory is this repository's root ({top.detail}); the cache "
              f"directory is named after exactly that path, so nothing here can be decided without it")
        return 3
    cache = cache_paths(top.path)
    if not os.path.isdir(repo_mem):
        # The cache is read before this answers, because the absence of the repo directory alone is not
        # evidence the convention does not apply here (CD4). A repo with no `.claude/memory/` whose
        # machine cache is already holding real memory files is the exact state this convention exists
        # to rescue, and returning 1 on the repo half alone files it `n/a` for good.
        held = [name for name in cache_entries(cache.memory) if os.path.isfile(os.path.join(cache.memory, name))]
        if held and not is_link(cache.memory):
            print(f"there is no {REPO_MEM_REL}/ in this repo, and this machine is holding "
                  f"{len(held)} memory file(s) for it outside the repo: {', '.join(held)}. Memory written "
                  f"through the cache reaches neither the other machine nor a fresh clone. Whether this "
                  f"repo should keep versioned memory at all is a decision about the repo — record n/a if "
                  f"it deliberately keeps none, and otherwise create {REPO_MEM_REL}/ and re-run, which "
                  f"carries those file(s) into it.")
            return 2
        # Positive evidence, per CD4: the committed directory this convention points at is absent, and
        # the machine holds nothing that belongs in it. This step never creates one.
        print(f"no {REPO_MEM_REL}/ in this repo and no memory file in this machine's cache for it — there "
              f"is nothing for the cache to point at, and this step never creates one")
        return 1
    if not os.path.lexists(cache.memory):
        variants = sibling_spellings(cache)
        if variants:
            print(f"this machine keeps no cache at {cache.memory}, but it does keep {', '.join(variants)} — "
                  f"the same repo under another spelling of its path, which the harness reads when a session "
                  f"is started that way. Which spelling this repo is opened under is not this step's guess: "
                  f"wire the one in use by hand, or re-run /adopt from the spelling you work in.")
            return 2
        print(f"{REPO_MEM_REL}/ is committed here and this machine keeps no memory cache for the repo yet, "
              f"so the link has never existed")
        return 0
    try:
        if os.path.samefile(cache.memory, repo_mem):
            # Read off the two inodes rather than inferred from an absence: the cache and the repo copy
            # are one directory, which is what a wired machine looks like — including one wired long
            # before this step existed.
            print(f"already wired: this machine's memory cache for this repo is {REPO_MEM_REL}/")
            return 1
    except OSError:
        pass
    if is_link(cache.memory):
        print(f"{cache.memory} is already {describe(cache.memory)}, which is not this repo's {REPO_MEM_REL}/. "
              f"Where that link should point, and what becomes of what it holds, is not this step's guess — "
              f"remove or repoint it by hand and re-run.")
        return 2
    if not os.path.isdir(cache.memory):
        print(f"{cache.memory} is {describe(cache.memory)} where the harness keeps a directory. This step "
              f"will not move it aside.")
        return 2
    clashing = collisions(cache.memory, repo_mem)
    if clashing:
        print(f"the un-versioned cache at {cache.memory} and this repo's {REPO_MEM_REL}/ both hold "
              f"{len(clashing)} name(s): {', '.join(clashing)}. Those are two versions of one memory and "
              f"merging them is not this step's guess — reconcile each by hand, leave one copy, and re-run.")
        return 2
    carried = cache_entries(cache.memory)
    print(f"{REPO_MEM_REL}/ is committed here and {cache.memory} is a plain directory holding "
          f"{len(carried)} file(s), none of which the repo copy already has")
    return 0


def cmd_apply(root: str, dry_run: bool) -> int:
    repo_mem = os.path.join(root, *REPO_MEM_REL.split("/"))
    code, note, cache = shape(root)
    if code == 0:
        # A second apply, and the reason it exits 0 rather than crashing or re-linking: the machine is
        # already in the target shape, so there is nothing to do and nothing to undo.
        print(f"already wired; {note}")
        return 0
    if cache is None:
        print(f"{note} — nothing was changed")
        return 3
    if not os.path.isdir(repo_mem):
        print(f"{note} — nothing was changed, and this step never creates {REPO_MEM_REL}/")
        return 3
    if os.path.lexists(cache.memory) and (is_link(cache.memory) or not os.path.isdir(cache.memory)):
        print(f"{cache.memory} is {describe(cache.memory)} rather than the plain directory this step "
              f"replaces with a link. Nothing was changed — resolve it by hand and re-run.")
        return 3
    clashing = collisions(cache.memory, repo_mem)
    if clashing:
        for name in clashing:
            print(f"CLASH       {os.path.join(cache.memory, name)}")
            print(f"            {os.path.join(repo_mem, name)}")
        print(f"{len(clashing)} name(s) are held by both the un-versioned cache and {REPO_MEM_REL}/. Those "
              f"are two versions of one memory; nothing was moved, nothing was linked, and which copy "
              f"survives is a human's call.")
        return 3
    carried = cache_entries(cache.memory)
    if dry_run:
        for name in carried:
            print(f"would move  {name} -> {REPO_MEM_REL}/{name}")
        print(f"{len(carried)} file(s) would move out of {cache.memory}, which would then become a link to "
              f"{REPO_MEM_REL}/ made by claude/scripts/link-project-memory.sh")
        return 0
    lines, failed = migrate(cache.memory, repo_mem)
    for line in lines:
        print(line)
    if failed:
        print(f"nothing was linked and every file still in {cache.memory} is untouched; a re-run picks up "
              f"the ones already carried across")
        return 3
    script_code, detail = run_link_script(root)
    if script_code:
        print(f"link-project-memory.sh stopped: {detail}")
        print(f"{len(carried)} file(s) are already in {REPO_MEM_REL}/ and nothing was deleted; a re-run "
              f"makes the link")
        return 3
    code, note, _ = shape(root)
    if code != 0:
        print(f"the link was attempted and the result is not the target shape: {note}")
        return 3
    for name in carried:
        found = os.path.isfile(os.path.join(repo_mem, name))
        print(f"{'ok         ' if found else 'LOST       '} {name} -> {REPO_MEM_REL}/{name}")
    if any(not os.path.isfile(os.path.join(repo_mem, name)) for name in carried):
        print(f"the link is in place but a file that was carried across is no longer in {REPO_MEM_REL}/ — "
              f"nothing further was done")
        return 3
    print(f"{note}; {len(carried)} file(s) carried out of the un-versioned cache first, each read back "
          f"before its original was removed")
    return 0


def cmd_verify(root: str) -> int:
    """Is this machine's cache for this repo the repo's own directory — never, did a script run here.

    A machine-scoped step is the one place where a fresh clone must read as pending, so the answer
    is re-derived from two inodes every time rather than from any record of the link being made.
    """
    code, note, _ = shape(root)
    print(note)
    return code


if __name__ == "__main__":
    raise SystemExit(_dispatch.run(__file__, cmd_probe, cmd_apply, cmd_verify))
