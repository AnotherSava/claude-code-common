"""Asking git what it hides — the one trustworthy answer to "does anybody maintain this file?".

Several rules turn on whether git hides a path, and none of them matches a pattern itself.
Re-implementing gitignore matching is how a check ends up confidently wrong about
`**/config/*.env`, or about which of two rules wins, so nothing here interprets a pattern.

Three measured facts shape every call below, and each one has an easy wrong version.

**Exit status, not `-v`, is what says "ignored".** The `-v` form exits 0 on a *negation* too,
because its status answers "did any pattern apply" and a `!` rule applies as much as an exclusion
does (learnings/gitignore-anchoring-and-scope.md). Measured: with `config/*.env` followed by
`!config/publish.env`, the `-v` form prints `.gitignore:2:!config/publish.env` and exits 0 while the
path is plainly not ignored. So the *plain* form decides — it prints only the paths that are
genuinely ignored — and `-v` is used afterwards, on paths already known to be ignored, purely to
name the rule behind each one. The two are not interchangeable, and git refuses `-v` with `-q`
outright: `fatal: cannot have both --quiet and --verbose`.

**The `--no-index` flag is what reads the rules rather than the history.** By default
`check-ignore` consults the index and reports a *tracked* path as not ignored, whatever the rules
say. A repo that once force-added a file it excludes would then answer "nothing is hidden" while the
rule still hides every new file beside it. A question about the rules passes the flag; a question
about whether anybody maintains a file must not — see `ignored_untracked` below.

**The `-z` flag governs both directions.** Output fields are `source`, `line number`, `pattern`,
`path`, and a pattern may hold a colon while a path may hold anything at all; NUL separation makes
the split exact instead of a regex guessing where the source ended
(learnings/git-porcelain-parsing.md). With `--stdin`, `-z` changes the *input* separator to NUL as
well, so the paths fed in are NUL-joined.

Every function here raises `GitRefused` rather than returning an empty set when git will not answer.
A rule that could not look must never read as a rule that passed: the runner turns the exception
into an unmeasured line and a non-zero exit, while a filtered-to-nothing set would pass silently.
"""

import os
import subprocess
from typing import NamedTuple

GIT_TIMEOUT = 30


class GitRefused(Exception):
    """Git would not answer, so what it hides here is unknown.

    Never softened into an empty set anywhere below. "Git hides none of these" and "git would not
    say" are different facts, and a rule handed the second as the first reports a clean tree on no
    evidence — the one failure mode a continuous check cannot afford, since every later reader
    trusts its silence.
    """


class Rule(NamedTuple):
    """One `check-ignore -v` record: which file, which line, which pattern, and for which path."""

    source: str  # as git prints it — repo-relative for a project file, absolute for the global one
    line_no: int
    pattern: str
    path: str


def git(root: str, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    """One git command against `root`, raising when git could not be run at all.

    A non-zero exit comes back as an ordinary result, because which codes are an answer differs per
    command: `check-ignore` exits 1 for "none of these paths is ignored", and `config --global` exits
    1 for "that key is unset", both of them answers. Being unable to start git at all is not, so it
    raises here rather than reaching a caller as a falsy object it might read as "no".
    """
    try:
        return subprocess.run(["git", "-C", root, *args], input=stdin, capture_output=True,
                              encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise GitRefused(f"git {' '.join(args[:2])} could not be run in {os.path.basename(root)} ({exc})") from exc


def _answered(done: subprocess.CompletedProcess[str], what: str) -> None:
    """Git either answered the question or it did not; 0 and 1 are the two answers it gives."""
    if done.returncode in (0, 1):
        return
    detail = (done.stderr or done.stdout or "").strip().splitlines()
    raise GitRefused(f"git {what} exited {done.returncode} rather than answering"
                     f"{' — ' + detail[0] if detail else ''}")


def ignored(root: str, paths: tuple[str, ...] | list[str]) -> set[str]:
    """Which of these paths the *rules* hide, whatever the index says.

    The plain form, deliberately: it prints a path only when that path is ignored, so a `!`
    re-include drops out of the output instead of arriving as a match. Feeding the whole set on one
    `--stdin` call also keeps this to a single fork however many paths are asked about.
    """
    if not paths:
        return set()
    done = git(root, "check-ignore", "-z", "--no-index", "--stdin", stdin="\0".join(paths) + "\0")
    _answered(done, "check-ignore --no-index")
    return {name for name in done.stdout.split("\0") if name}


def ignored_untracked(root: str, paths: tuple[str, ...] | list[str]) -> set[str]:
    """Which of these paths git hides *and* nobody has committed.

    The plain form without `--no-index`, and that one omission is the whole difference from
    `ignored` above. That function asks about the rules, which is the right question for a rule
    asserting that a path this repo commits is not excluded. Asked about a *file*, the same question
    answers "the rules match this path" and says nothing about whether anyone maintains it. Measured
    on a scratch repo: with `/scratch/` ignored and `scratch/package.json` committed through
    `git add -f`, the `--no-index` form exits 0 and the plain form exits 1, and staging the file
    alone is enough to flip the plain form while `--no-index` never moves.

    So the plain form is exactly the predicate "git hides this and nobody has claimed it": it
    consults the index first and reports a tracked path as not ignored whatever the rules say. Being
    in the index settles it — someone committed the file, it arrives on a fresh clone, and a change
    to it is a diff a human reviews.

    Three ways of not knowing all raise, and the third is the one that looks like an answer: one
    path inside a submodule aborts the whole batch with exit 128 *after* printing part of its
    output, so the partial stdout must never be read as the result.

    The `root` argument is asserted to be the work tree's own top level first, because
    `check-ignore` run anywhere *under* a repo answers quite happily using that ancestor's rules —
    so "a repo answered" is not "the repo I meant answered". A scratch tree placed inside a checkout
    that hides `tmp/` would have every file in it reported as hidden, and a caller filtering on that
    would come back empty while looking like it had looked. Compared with `samefile` rather than as
    strings, since neither spelling nor case decides what is one directory on these two machines
    (learnings/comparing-paths-symlinks-and-case.md).

    And only a hide the *repo* carries is reported, which is the difference between an answer about
    a commit and an answer about a checkout. The per-clone `.git/info/exclude` and the per-machine
    global excludes file both return exit 0 exactly like a committed `.gitignore`, so without this
    two machines derive different sets from one tree. Carried one source further than
    `source_is_in_repo` goes: that helper answers "is this file in the working tree", while a
    `.gitignore` written and never committed is in the working tree and in no clone, so the cited
    source must also be tracked.
    """
    if not paths:
        return set()
    top = git(root, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or not top.stdout.strip():
        raise GitRefused(f"{root} is not the top of a git work tree git will speak about")
    try:
        same = os.path.samefile(top.stdout.strip(), root)
    except (OSError, ValueError):
        same = False
    if not same:
        raise GitRefused(f"git answers for {top.stdout.strip()} rather than {root}, so the rules it applied "
                         f"are another repository's")
    done = git(root, "check-ignore", "-z", "--stdin", stdin="\0".join(paths) + "\0")
    _answered(done, "check-ignore")
    hidden = {name for name in done.stdout.split("\0") if name}
    if not hidden:
        return set()
    rules = rules_for(root, sorted(hidden))
    unattributed = sorted(name for name in hidden if name not in rules)
    if unattributed:
        raise GitRefused(f"git hid {len(unattributed)} path(s) and then named no rule for them "
                         f"({', '.join(unattributed[:3])}), so whether the repo or this machine hides them "
                         f"is unknown")
    in_repo = {name for name in hidden if source_is_in_repo(root, rules[name].source)}
    if not in_repo:
        return set()
    sources = sorted({rules[name].source for name in in_repo})
    listed = git(root, "ls-files", "-z", "--", *sources)
    if listed.returncode != 0:
        raise GitRefused("git would not say which of the ignore files it cited are tracked, so whether a "
                         "clone hides these paths too was never established")
    tracked = {name for name in listed.stdout.split("\0") if name}
    return {name for name in in_repo if rules[name].source in tracked}


def rules_for(root: str, paths: tuple[str, ...] | list[str]) -> dict[str, Rule]:
    """The winning rule behind each path, for paths already known to be ignored.

    Never used to decide whether a path is ignored — see the module docstring for the negation that
    makes this form's exit status say the opposite of what it looks like.
    """
    if not paths:
        return {}
    done = git(root, "check-ignore", "-z", "-v", "--no-index", "--stdin", stdin="\0".join(paths) + "\0")
    _answered(done, "check-ignore -v")
    fields = done.stdout.split("\0")
    out: dict[str, Rule] = {}
    for index in range(0, len(fields) - 3, 4):
        source, line_no, pattern, path = fields[index:index + 4]
        out[path] = Rule(source, int(line_no) if line_no.isdigit() else 0, pattern, path)
    return out


def ignored_on_disk(root: str) -> list[str]:
    """Every ignored path git currently sees, expanded exactly where a caller has to see the files.

    The mode is `--ignored=matching`, and the default `--ignored` is the trap it avoids. The default
    collapses a directory to one entry whenever *everything inside it* is ignored, even when the
    directory itself matches no pattern at all — so a repo hiding `web/config/deploy.env` inside an
    otherwise-empty `web/` reports `!! web/` and nothing else, and a caller asking which rule hides
    which file is handed a directory `check-ignore` attributes to no rule. Measured on a scratch repo
    in exactly that shape: `--porcelain --ignored` prints `!! web/`, while `--ignored=matching`
    prints `!! web/config/deploy.env`.

    The matching mode still collapses a directory that *does* match a pattern, which is the
    granularity that keeps this affordable: `node_modules/` stays one entry rather than becoming
    thirty thousand. Measured across the fleet's five largest repos it returns within three entries
    of the default mode everywhere, and runs faster — 13ms against 1571ms on the largest.

    Parsed with `-z` so a path holding a quote or a non-ASCII character arrives whole
    (learnings/git-porcelain-parsing.md).
    """
    done = git(root, "status", "--porcelain", "-z", "--ignored=matching")
    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip().splitlines()
        raise GitRefused(f"git status --ignored exited {done.returncode} rather than listing what it hides"
                         f"{' — ' + detail[0] if detail else ''}")
    return [entry[3:] for entry in done.stdout.split("\0") if entry.startswith("!! ")]


def source_is_in_repo(root: str, source: str) -> bool:
    """Is the file git named one this repo owns, rather than the global excludes or .git/info/exclude.

    Git prints a project file as a repo-relative path and the global one as an absolute path, so the
    test is anchored on that rather than on a basename — a repo may hold a nested `.gitignore` at any
    depth, and the repo-relative `.git/info/exclude` is no more this repo's own than the global file
    is, since neither is committed.
    """
    plain = source.replace("\\", "/")
    if os.path.isabs(plain) or plain.startswith(".git/"):
        return False
    return os.path.isfile(os.path.join(root, *plain.split("/")))
