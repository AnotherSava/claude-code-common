"""What v2 and v3 both need to decide a gitignore question by running git rather than by reading text.

Two steps edit `.gitignore` files, and both of them answer "is this path hidden?" the only way
that is trustworthy — by asking `git check-ignore` — rather than by matching patterns themselves.
Re-implementing gitignore matching is how a step ends up confidently wrong about `**/config/*.env`
or about which of two rules wins, so nothing here interprets a pattern.

Three measured facts shape every call below, and each one has an easy wrong version.

**Exit status, not `-v`, is what says "ignored".** `git check-ignore -v` exits 0 on a *negation*
too, because its status answers "did any pattern apply" and a `!` rule applies as much as an
exclusion does (learnings/gitignore-anchoring-and-scope.md). Measured here: with `config/*.env`
followed by `!config/publish.env`, the `-v` form prints `.gitignore:2:!config/publish.env` and
exits 0 while the path is plainly not ignored. So the *plain* form decides — it prints only the
paths that are genuinely ignored — and `-v` is used afterwards, on paths already known to be
ignored, purely to name the rule behind each one. The two are not interchangeable and git refuses
`-v` with `-q` outright: `fatal: cannot have both --quiet and --verbose`.

**`--no-index` is what reads the rules rather than the history.** By default `check-ignore`
consults the index and reports a *tracked* path as not ignored, whatever the rules say. A repo
that once force-added a file it excludes would then answer "no deviation" while the rule still
hides every new file beside it. The question these steps ask is about the rules, so every call
passes `--no-index`.

**`-z` for both directions.** Output fields are `source`, `line number`, `pattern`, `path`, and a
pattern may hold a colon and a path may hold anything at all; NUL separation makes the split exact
instead of a regex guessing where the source ended (learnings/git-porcelain-parsing.md). With
`--stdin`, `-z` changes the *input* separator to NUL as well, so the paths fed in are NUL-joined.
"""

import os
import subprocess
from typing import NamedTuple

# `git check-ignore` exits 1 for "none of these paths is ignored", which is an answer and not a
# failure; 128 is the failure — outside a work tree, or a git that will not run on this tree.
GIT_TIMEOUT = 30


class Rule(NamedTuple):
    """One `check-ignore -v` record: which file, which line, which pattern, and for which path."""

    source: str  # as git prints it — repo-relative for a project file, absolute for the global one
    line_no: int
    pattern: str
    path: str


class Block(NamedTuple):
    """A run of lines between blank lines: a leading comment header, then its content lines."""

    start: int  # index of the first line of the block in the file
    header: list[int]  # indices of the leading comment lines
    content: list[int]  # indices of the pattern lines below them


def git(root: str, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess | None:
    """One git command against `root`, or None when git could not be run at all.

    None and a non-zero exit are different facts: the first means the question was never put,
    which a step reports rather than reading as "nothing is ignored".
    """
    try:
        return subprocess.run(["git", "-C", root, *args], input=stdin, capture_output=True,
                              encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def ignored(root: str, paths: tuple[str, ...] | list[str]) -> set[str] | None:
    """Which of these paths git actually hides. None when git could not be asked.

    The plain form, deliberately: it prints a path only when that path is ignored, so a `!`
    re-include drops out of the output instead of arriving as a match. Feeding the whole set on
    one `--stdin` call also keeps this to a single fork however many paths are asked about
    (idempotence rule 4).
    """
    if not paths:
        return set()
    done = git(root, "check-ignore", "-z", "--no-index", "--stdin", stdin="\0".join(paths) + "\0")
    if done is None or done.returncode not in (0, 1):
        return None
    return {name for name in done.stdout.split("\0") if name}


def ignored_untracked(root: str, paths: tuple[str, ...] | list[str]) -> tuple[set[str], str]:
    """Which of these paths git hides *and* nobody has committed, or the reason it would not say.

    The plain form without `--no-index`, and that one omission is the whole difference from
    `ignored` above. That function asks about the rules, which is the right question for v2 and
    v3 — a repo that once force-added a file it excludes must not report "no deviation" while the
    rule still hides every new file beside it. Asked about a *file*, the same question answers
    "the rules match this path" and says nothing about whether anyone maintains it. Measured here
    on a scratch repo: with `/scratch/` ignored and `scratch/package.json` committed through
    `git add -f`, `--no-index` exits 0 and the plain form exits 1, and staging the file alone is
    enough to flip the plain form while `--no-index` never moves.

    So the plain form is exactly the predicate "git hides this and nobody has claimed it": it
    consults the index first and reports a tracked path as not ignored whatever the rules say.
    Being in the index settles it — someone committed the file, it arrives on a fresh clone, and
    a change to it is a diff a human reviews.

    The reason comes back beside the set rather than as the `None` its sibling returns, because
    this caller has to *report* why it could not look. One path inside a submodule aborts the
    whole batch with exit 128 after printing part of its answer, so the partial stdout must never
    be read as the answer: `git check-ignore` declining to speak for a path another repo owns is
    more useful than a confident wrong one, and the caller prints git's own sentence and stops.

    `root` is asserted to be the work tree's own top level first, because `check-ignore` run
    anywhere *under* a repo answers quite happily using that ancestor's rules — so "a repo
    answered" is not "the repo I meant answered". A scratch copy of a fixture placed inside a
    checkout that hides `tmp/` would have every file in it reported as hidden, and a caller
    filtering on that would silently come back empty while looking like it had looked. Compared
    with `samefile` rather than as strings, for the case `_own_fixtures` opens on.

    And only a hide the *repo* carries is reported, which is the difference between an answer
    about a commit and an answer about a checkout. `.git/info/exclude` is per-clone and the global
    excludes file is per-machine; a path hidden by either returns exit 0 exactly like one hidden
    by a committed `.gitignore`, so without this two machines derive different sets from one tree
    and a step recorded on the first can fail on the second. Note which direction that fails in:
    v2 and v3 assert paths are *not* ignored, so a machine-local rule makes them fail loudly,
    while a caller narrowing a set the way this one does would lose entries in silence.

    Carried one source further than `source_is_in_repo` goes: that helper answers "is this file in
    the working tree", which is what v2 and v3 want, while a `.gitignore` written and never
    committed is in the working tree and in no clone. So the cited source must also be tracked.
    """
    if not paths:
        return set(), ""
    top = git(root, "rev-parse", "--show-toplevel")
    if top is None or top.returncode != 0 or not top.stdout.strip():
        return set(), f"{root} is not the top of a git work tree git will speak about"
    try:
        same = os.path.samefile(top.stdout.strip(), root)
    except (OSError, ValueError):
        same = False
    if not same:
        return set(), (f"git answers for {top.stdout.strip()} rather than {root}, so the rules it applied "
                       f"are another repository's")
    done = git(root, "check-ignore", "-z", "--stdin", stdin="\0".join(paths) + "\0")
    if done is None:
        return set(), "git could not be run at all, so which paths it hides was never established"
    if done.returncode not in (0, 1):
        detail = (done.stderr or done.stdout or "").strip().splitlines()
        return set(), (f"git check-ignore exited {done.returncode} rather than answering"
                       f"{' — ' + detail[0] if detail else ''}")
    hidden = {name for name in done.stdout.split("\0") if name}
    if not hidden:
        return set(), ""
    # Only a rule the repo carries counts. `.git/info/exclude` is per-clone and the global excludes
    # file is per-machine, and neither travels — so a hide from either makes this answer a property
    # of the checkout rather than of the commit, and two machines compute different sets for one
    # tree. Measured: all three sources return exit 0 from the form above, indistinguishably.
    # `source_is_in_repo` below is exactly this distinction and already existed for v2 and v3.
    rules = rules_for(root, sorted(hidden))
    if rules is None:
        return set(), ("git would not name the rule behind each hidden path, so which of them a clone "
                       "hides too was never established")
    unattributed = sorted(name for name in hidden if name not in rules)
    if unattributed:
        return set(), (f"git hid {len(unattributed)} path(s) and then named no rule for them "
                       f"({', '.join(unattributed[:3])}), so whether the repo or this machine hides them is unknown")
    in_repo = {name for name in hidden if source_is_in_repo(root, rules[name].source)}
    if not in_repo:
        return set(), ""
    # In the repo is not yet in the commit. `source_is_in_repo` tests that the file is on disk here,
    # which is the right question for v2 and v3 and one source short of the right question for this
    # one: a `.gitignore` written but never committed hides paths on this machine and on no clone, so
    # honouring it puts the checkout back into an answer that is supposed to be about the tree.
    sources = sorted({rules[name].source for name in in_repo})
    listed = git(root, "ls-files", "-z", "--", *sources)
    if listed is None or listed.returncode != 0:
        return set(), ("git would not say which of the ignore files it cited are tracked, so whether a clone "
                       "hides these paths too was never established")
    tracked = {name for name in listed.stdout.split("\0") if name}
    return {name for name in in_repo if rules[name].source in tracked}, ""


def rules_for(root: str, paths: tuple[str, ...] | list[str]) -> dict[str, Rule] | None:
    """The winning rule behind each path, for paths already known to be ignored.

    Never used to decide whether a path is ignored — see the module docstring for the negation
    that makes this form's exit status say the opposite of what it looks like.
    """
    if not paths:
        return {}
    done = git(root, "check-ignore", "-z", "-v", "--no-index", "--stdin", stdin="\0".join(paths) + "\0")
    if done is None or done.returncode not in (0, 1):
        return None
    fields = done.stdout.split("\0")
    out: dict[str, Rule] = {}
    for index in range(0, len(fields) - 3, 4):
        source, line_no, pattern, path = fields[index:index + 4]
        out[path] = Rule(source, int(line_no) if line_no.isdigit() else 0, pattern, path)
    return out


def ignored_on_disk(root: str) -> list[str] | None:
    """Every ignored path git currently sees, expanded exactly where a caller has to see the files.

    The mode is `--ignored=matching`, and the default `--ignored` is the trap it avoids. The
    default collapses a directory to one entry whenever *everything inside it* is ignored, even
    when the directory itself matches no pattern at all — so a repo hiding `web/config/deploy.env`
    inside an otherwise-empty `web/` reports `!! web/` and nothing else, and a caller asking which
    rule hides which file is handed a directory `check-ignore` attributes to no rule. Measured on a
    scratch repo in exactly that shape: `--porcelain --ignored` prints `!! web/`, while
    `--ignored=matching` prints `!! web/config/deploy.env`.

    The matching mode still collapses a directory that *does* match a pattern, which is the
    granularity that keeps this affordable: `node_modules/` stays one entry rather than becoming
    thirty thousand. Measured across the fleet's five largest repos it returns within three entries
    of the default mode everywhere, and runs faster — 13ms against 1571ms on the largest.

    Parsed with `-z` so a path holding a quote or a non-ASCII character arrives whole
    (learnings/git-porcelain-parsing.md).
    """
    done = git(root, "status", "--porcelain", "-z", "--ignored=matching")
    if done is None or done.returncode != 0:
        return None
    return [entry[3:] for entry in done.stdout.split("\0") if entry.startswith("!! ")]


def source_is_in_repo(root: str, source: str) -> bool:
    """Is the file git named one this repo owns, rather than the global excludes or .git/info/exclude.

    Git prints a project file as a repo-relative path and the global one as an absolute path, so
    the test is anchored on that rather than on a basename — a repo may hold a nested `.gitignore`
    at any depth, and `.git/info/exclude` is repo-relative yet no more editable by a step than the
    global file is, since neither is committed.
    """
    plain = source.replace("\\", "/")
    if os.path.isabs(plain) or plain.startswith(".git/"):
        return False
    return os.path.isfile(os.path.join(root, *plain.split("/")))


def read_lines(path: str) -> list[str] | None:
    """A file's lines without their endings, or None when it cannot be read."""
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return None


def write_lines(path: str, lines: list[str]) -> None:
    """Rewrite a gitignore, LF-terminated whatever the platform, with one trailing newline.

    newline="\\n" because these repos are worked on from a Windows machine and a macOS one, and a
    step that let the platform choose would turn a one-line deletion into a whole-file diff
    (idempotence rule 4).
    """
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(f"{line}\n" for line in lines))


def escaped_lines(lines: list[str]) -> list[str]:
    """Lines carrying a backslash, reported verbatim with their number so a step can abort.

    Gitignore gives the backslash a meaning these steps do not implement: `foo\\ ` keeps a trailing
    space that `.strip()` silently eats, and `\\#file` is a pattern rather than a comment. Comparing
    a stripped copy of such a line against the global excludes file is comparing something the
    author did not write, and deleting it on the strength of that match removes a rule nobody
    matched. Abort rather than skip (idempotence rule 6), and rather than guess.
    """
    return [f"line {number}: {line}" for number, line in enumerate(lines, 1)
            if "\\" in line and not line.lstrip().startswith("#")]


def blocks(lines: list[str]) -> list[Block]:
    """Group a gitignore into blank-line-separated blocks, each a comment header plus its patterns.

    This is what lets a deletion take the comment with it exactly when the comment has nothing
    left to describe, and leave it alone when it still heads other patterns — `# Ralphex` above
    three lines keeps its place when one of them goes, while a comment whose only line is deleted
    would otherwise sit there introducing the blank space where its rule used to be.
    """
    out: list[Block] = []
    start = 0
    while start < len(lines):
        if not lines[start].strip():
            start += 1
            continue
        end = start
        while end < len(lines) and lines[end].strip():
            end += 1
        head = start
        while head < end and lines[head].lstrip().startswith("#"):
            head += 1
        out.append(Block(start, list(range(start, head)), list(range(head, end))))
        start = end
    return out


def without(lines: list[str], doomed: set[int]) -> tuple[list[str], list[int]]:
    """The file with those line indices gone, plus every extra index the removal carried with it.

    A block emptied by the removal goes entirely, header and all, together with one adjacent blank
    line so the file does not gain a doubled gap where a rule used to be. A block with content
    left keeps its header, because that header still describes what remains.
    """
    removing = set(doomed)
    for block in blocks(lines):
        if block.content and set(block.content) <= removing:
            removing.update(block.header)
    for block in blocks(lines):
        indices = set(block.header) | set(block.content)
        if not indices <= removing:
            continue
        after = max(indices) + 1
        before = min(indices) - 1
        if after < len(lines) and not lines[after].strip():
            removing.add(after)
        elif before >= 0 and not lines[before].strip():
            removing.add(before)
    kept = [index for index in range(len(lines)) if index not in removing]
    # A block removed at the foot of the file can leave the blank line above it behind, when the
    # block removed just before it already claimed that blank as its own trailing gap. Trimmed
    # only where the file did not already end on a blank line, so this cannot touch a shape the
    # author chose.
    if lines and lines[-1].strip():
        while kept and not lines[kept[-1]].strip():
            removing.add(kept.pop())
    return [lines[index] for index in kept], sorted(removing - set(doomed))


def restore(root: str, originals: dict[str, list[str] | None]) -> None:
    """Put every rewritten .gitignore back, so a failed apply leaves no rule half-removed.

    Shared because both gitignore steps rewrite the same files the same way, and a rollback that
    worked in one of them while quietly diverging in the other is the failure this cannot afford:
    the tree it leaves behind is the input to whatever the user does next.
    """
    for source, lines in originals.items():
        if lines is not None:
            try:
                write_lines(os.path.join(root, *source.split("/")), lines)
            except OSError as exc:
                print(f"COULD NOT RESTORE  {source} ({exc}) — restore it with git checkout -- {source}")
