#!/usr/bin/env python3
"""v2 — stop a project .gitignore hiding a file the conventions require committed.

Five paths in this system are meant to be in the repo: the project settings, the committed
memory directory, the memo backlog, the convention record `/adopt` writes, and the transcrypt-
encrypted publish config. A project `.gitignore` rule that covers any of them — or anything
*inside* the two that are directories — makes the file silently never stage: `git add` says
nothing, `git status` shows nothing, and the loss surfaces on the other machine as a file that was
never there. That is the failure `config/publish.env` was taken out of the global excludes to end,
and one repo still holds a `**/config/*.env` line that would reproduce it the day it publishes.

The decision is taken from `git check-ignore`, never from the text of `.gitignore`, so a pattern
that reaches one of these paths by a route nobody predicted still fails. The traps in doing that
correctly — why `-v` is the wrong form to read a verdict from, why `--no-index` is required, why
`-z` — are in `_gitignore.py` beside the calls they govern.

One shape is a refusal rather than a fix. Git will not re-include a path whose parent directory
is excluded, so a repo hiding `.claude/` wholesale cannot be repaired by adding `!.claude/memos/`
below it; the entry has to become `.claude/*` with explicit `!` re-includes, which changes what
every other file under `.claude/` does and is a human's edit. This step names that and stops.

    gitignore-unhides-committed.py probe  <repo-root>              0 applies · 1 no · 2 ask · 3 error
    gitignore-unhides-committed.py apply  <repo-root> [--dry-run]  0 done · 3 stopped, files intact
    gitignore-unhides-committed.py verify <repo-root>              0 in shape · 2 unobservable · 3 not

The last line `apply` prints is the record note; the lines above it are the per-path evidence
behind it. The note is one line and carries no tab, because it becomes a field in a TSV record.
"""

import os
import sys
from typing import NamedTuple

import _dispatch
import _gitignore
from _gitignore import Rule

# Emit UTF-8 whatever the console codepage is. This prints gitignore lines back verbatim, and a
# non-ASCII one through Windows' cp1252 default raises rather than prints, turning a healthy run
# into an exit 3.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Every path the conventions require committed. Directories carry a trailing slash so git is told
# what kind of thing it is being asked about; the file paths are the ones a rule most often
# catches by accident, since each sits beside a sibling that genuinely is machine-local.
REQUIRED = (".claude/settings.json", ".claude/memory/", ".claude/memos/",
            ".claude/conventions.tsv", "config/publish.env")

# Asking about a directory answers only whether *the directory* is ignored, and a rule reaching its
# contents instead — `.claude/memos/*.md`, `.claude/memory/project_*.md` — is invisible to that
# question. Measured on a scratch repo carrying both: every memo and every project-memory file was
# hidden while `verify` exited 0 and `probe` exited 1, which is this step's own docstring failure
# recorded as `applied`. So the files git currently hides inside a required directory are asked
# about by name alongside the directory itself.
REQUIRED_DIRS = tuple(path for path in REQUIRED if path.endswith("/"))


class Edit(NamedTuple):
    """One planned change to one rule of one project .gitignore."""

    source: str  # repo-relative path of the .gitignore holding the rule
    rule: Rule
    paths: list[str]  # the required paths this rule currently hides
    delete: bool  # True: the pattern names the path exactly, so the line goes
    reincludes: list[str]  # the `!` entries appended instead, in the .gitignore's own terms


def ancestors(path: str) -> list[str]:
    """Every directory above a repo-relative path, deepest first, each with a trailing slash."""
    parts = path.strip("/").split("/")[:-1]
    return ["/".join(parts[:depth]) + "/" for depth in range(len(parts), 0, -1)]


def relative_to_source(source: str, path: str) -> str:
    """A repo-relative path rewritten relative to the directory holding the .gitignore.

    A rule in `config/.gitignore` reading `publish.env` names the same file as a root rule reading
    `config/publish.env`, and both a comparison against the pattern and a `!` re-include have to
    be written in the nested file's own terms or they name something else entirely.
    """
    base = os.path.dirname(source.replace("\\", "/"))
    trailing = "/" if path.endswith("/") else ""
    if not base:
        return path
    return os.path.relpath(path.rstrip("/"), base).replace(os.sep, "/") + trailing


def names_exactly(rule: Rule, path: str) -> bool:
    """Does this pattern name that one path and nothing else.

    Compared with the anchoring marks stripped from both sides: `/x`, `x` and `x/` all name the
    same entry to a reader deciding whether the line exists solely to hide it.
    """
    pattern = rule.pattern.strip("/")
    pattern = pattern[3:] if pattern.startswith("**/") else pattern
    return pattern == relative_to_source(rule.source, path).strip("/")


def covering_dir(path: str) -> str | None:
    """Which required directory this path sits inside, if any."""
    return next((base for base in REQUIRED_DIRS if path.startswith(base) and path != base), None)


def asked_about(root: str) -> list[str] | None:
    """The required paths, plus whatever git already hides inside a required directory.

    The second half is what a static list cannot hold: a rule naming the contents of a directory
    rather than the directory is a different question from the one `REQUIRED` asks, and no
    enumeration of filenames could anticipate the next memo. Asking git which paths it hides today
    and keeping the ones under a required directory turns that into an answer read off the tool.
    """
    on_disk = _gitignore.ignored_on_disk(root)
    if on_disk is None:
        return None
    inside = {path for path in on_disk if covering_dir(path)}
    return list(REQUIRED) + sorted(inside - set(REQUIRED))


def find_hidden(root: str) -> tuple[set[str] | None, dict[str, Rule], list[str]]:
    """Which asked-about paths are hidden here, the rule behind each, and everything asked.

    (None, {}, []) when git refuses, which is a different fact from "nothing is hidden" and is
    reported as such rather than read as a pass.
    """
    asked = asked_about(root)
    if asked is None:
        return None, {}, []
    hidden = _gitignore.ignored(root, asked)
    if hidden is None:
        return None, {}, []
    return hidden, _gitignore.rules_for(root, sorted(hidden)) or {}, asked


def describe(path: str, rule: Rule | None) -> str:
    return f"{path} <- {rule.source}:{rule.line_no} {rule.pattern}" if rule else f"{path} <- rule unknown"


def reinclude_token(source: str, path: str) -> str:
    """The `!` entry that unhides this path, written in the terms of the .gitignore holding it.

    A path hidden *inside* a required directory is re-included by the directory rather than by its
    own name. Re-including one file leaves the next one hidden, so `.claude/memos/one.md` would
    pass this step's own assertion while the memo written an hour later never stages —
    `!.claude/memos/**` covers the file that does not exist yet, verified on a scratch repo by
    adding a second memo after the edit and asking git about both.
    """
    base = covering_dir(path)
    return relative_to_source(source, base) + "**" if base else relative_to_source(source, path)


def plan(root: str, hidden: set[str], rules: dict[str, Rule]) -> tuple[list[Edit], list[str]]:
    """One edit per ignoring rule, or a refusal naming what a human has to decide instead."""
    refusals: list[str] = []
    blocked = _gitignore.ignored(root, sorted({parent for path in hidden for parent in ancestors(path)}))
    if blocked is None:
        return [], ["git could not be asked whether the parent directories of these paths are themselves ignored"]
    by_rule: dict[tuple[str, int], list[str]] = {}
    for path in sorted(hidden):
        rule = rules.get(path)
        if rule is None:
            refusals.append(f"{path} is ignored but git named no rule for it, so there is nothing to edit")
            continue
        if not _gitignore.source_is_in_repo(root, rule.source):
            refusals.append(f"{describe(path, rule)} — that file is not part of this repository, and this "
                            f"step edits only a committed project .gitignore")
            continue
        caught = [parent for parent in ancestors(path) if parent in blocked]
        if caught:
            refusals.append(f"{describe(path, rule)} — but {caught[0]} is itself excluded, and git cannot "
                            f"re-include a path through an excluded directory. The entry has to become "
                            f"{caught[0].rstrip('/')}/* with an explicit ! re-include per path that stays "
                            f"committed, which changes what every other file under it does.")
            continue
        by_rule.setdefault((rule.source, rule.line_no), []).append(path)
    edits: list[Edit] = []
    for (source, line_no), paths in sorted(by_rule.items()):
        rule = rules[paths[0]]
        exact = len(paths) == 1 and names_exactly(rule, paths[0])
        tokens = [] if exact else sorted({reinclude_token(source, path) for path in paths})
        edits.append(Edit(source, rule, paths, exact, tokens))
    return edits, refusals


def rewrite_file(root: str, source: str, edits: list[Edit]) -> tuple[list[str], str]:
    """The rewritten lines for one .gitignore, or a reason this step will not rewrite it.

    Every edit to one file is resolved together, because a deletion moves every line below it and
    the line numbers git reported were all read off the same original. Applying them one at a time
    would have the second edit reading a file the first has already shifted.
    """
    path = os.path.join(root, *source.split("/"))
    lines = _gitignore.read_lines(path)
    if lines is None:
        return [], f"{source} could not be read as UTF-8 text"
    escaped = _gitignore.escaped_lines(lines)
    if escaped:
        return [], (f"{source} holds {len(escaped)} line(s) carrying a backslash, whose meaning this "
                    f"step does not implement: " + "; ".join(escaped))
    doomed: set[int] = set()
    appended: list[str] = []
    for edit in edits:
        index = edit.rule.line_no - 1
        if not 0 <= index < len(lines):
            return [], f"{source} has no line {edit.rule.line_no}, where git reported {edit.rule.pattern!r}"
        if lines[index].strip() != edit.rule.pattern.strip():
            return [], (f"{source} line {edit.rule.line_no} reads {lines[index].strip()!r} where git "
                        f"reported {edit.rule.pattern!r}; the file changed under this step")
        if edit.delete:
            doomed.add(index)
        else:
            appended.extend(f"!{entry}" for entry in edit.reincludes)
    kept, carried = _gitignore.without(lines, doomed)
    for extra in carried:
        # Printed verbatim rather than counted: a comment that described only the deleted rule goes
        # with it, and a reader has to be able to see what text left the file.
        print(f"  carried with it  {source}:{extra + 1}  {lines[extra] or '(blank line)'}")
    if appended:
        note = "# Re-included by convention v2: a pattern above also covers a file this repo commits."
        kept = kept + ([""] if kept and kept[-1].strip() else []) + [note] + appended
    return kept, ""


def cmd_probe(root: str) -> int:
    hidden, rules, asked = find_hidden(root)
    if hidden is None:
        print("git check-ignore could not be run here, so whether anything is hidden was never answered")
        return 3
    if not hidden:
        # Positive evidence read off the tool itself (CD4), not inferred from a file's absence: git
        # was handed every required path, plus whatever it hides inside one of the required
        # directories, and named none of them. A repo holding none of those files on disk answers
        # this the same way, which is right — the question is about the rules.
        print(f"git check-ignore, asked about all {len(asked)} required paths, names none of them as "
              f"ignored: {', '.join(asked)}")
        return 1
    outside = [path for path in sorted(hidden)
               if path in rules and not _gitignore.source_is_in_repo(root, rules[path].source)]
    for path in sorted(hidden):
        print(f"hidden  {describe(path, rules.get(path))}")
    if len(outside) == len(hidden):
        print("Every one of those rules lives outside this repository — the global excludes file or "
              ".git/info/exclude — and this step edits only a committed project .gitignore. Which of the "
              "two should give way is a decision about every repo on this machine, not about this one: "
              "remove the rule there, or re-include the path in this repo's .gitignore by hand.")
        return 2
    print(f"{len(hidden) - len(outside)} of the {len(asked)} required paths are hidden by a rule in a "
          f"committed .gitignore in this repo")
    return 0


def cmd_verify(root: str) -> int:
    """Is no required path hidden here — asked of git, not of the text of any .gitignore.

    Non-vacuous by construction: the assertion is the output of a command that has to run inside a
    work tree, so an empty directory cannot answer 0. A repo owning no .gitignore at all passes,
    and correctly — the shape is "nothing hides these paths", not "a file was edited".
    """
    hidden, rules, asked = find_hidden(root)
    if hidden is None:
        print("git check-ignore could not be run here, so whether these paths are hidden is not a shape "
              "this script can observe")
        return 2
    if not hidden:
        print(f"none of the {len(asked)} required paths is ignored: {', '.join(asked)}")
        return 0
    for path in sorted(hidden):
        print(f"hidden  {describe(path, rules.get(path))}")
    print(f"{len(hidden)} required path(s) are hidden, so a file this repo is meant to commit would "
          f"silently never stage")
    return 3


def cmd_apply(root: str, dry_run: bool) -> int:
    hidden, rules, asked = find_hidden(root)
    if hidden is None:
        print("git check-ignore could not be run here — nothing was changed")
        return 3
    if not hidden:
        # A second apply, and the shape it reaches is the same as the first one's. Exiting 0 rather
        # than 1 or a crash: 1 means "does not apply" everywhere else in this system, and a step
        # that raises on its own finished work is the failure the idempotence assertion exists for.
        print(f"already in the target shape: none of the {len(asked)} required paths is ignored")
        return 0
    edits, refusals = plan(root, hidden, rules)
    if refusals:
        for refusal in refusals:
            print(f"REFUSED  {refusal}")
        print("Nothing was changed. Each of those needs a human's edit, then re-run this step.")
        return 3
    by_file: dict[str, list[Edit]] = {}
    for edit in edits:
        by_file.setdefault(edit.source, []).append(edit)
        for path in edit.paths:
            action = "delete the line" if edit.delete else f"append !{reinclude_token(edit.source, path)}"
            print(f"{'would fix' if dry_run else 'fixing  '}  {describe(path, edit.rule)} — {action}")
    written: dict[str, list[str]] = {}
    for source, group in by_file.items():
        lines, problem = rewrite_file(root, source, group)
        if problem:
            print(f"REFUSED  {problem}")
            print("Nothing was changed.")
            return 3
        written[source] = lines
    if dry_run:
        print(f"{len(edits)} rule(s) in {len(written)} project .gitignore file(s) would stop hiding "
              f"{len(hidden)} required path(s)")
        return 0
    originals = {source: _gitignore.read_lines(os.path.join(root, *source.split("/"))) for source in written}
    try:
        for source, lines in written.items():
            _gitignore.write_lines(os.path.join(root, *source.split("/")), lines)
    except OSError as exc:
        _gitignore.restore(root, originals)
        print(f"could not write {getattr(exc, 'filename', '?')} ({exc}) — every .gitignore was put back as it was")
        return 3
    still = _gitignore.ignored(root, asked)
    if still is None:
        _gitignore.restore(root, originals)
        print("git check-ignore could not be re-run to prove the edit took — every .gitignore was put back as it was")
        return 3
    # Per path and never on a count: one path freed while another stays hidden passes any tally,
    # and the tally is what would then be recorded as the note (learnings/git-stash-pull-safety.md).
    failed = False
    for path in sorted(hidden):
        if path in still:
            print(f"STILL HIDDEN  {path}")
            failed = True
        else:
            print(f"ok            {path} is no longer ignored")
    appeared = sorted(still - hidden)
    for path in appeared:
        print(f"NEWLY HIDDEN  {path}")
    if failed or appeared:
        _gitignore.restore(root, originals)
        print("every .gitignore was put back as it was — nothing is left half-edited")
        return 3
    print(f"{len(hidden)} required path(s) unhidden by editing {len(written)} project .gitignore file(s): "
          f"{', '.join(sorted(hidden))}; each asserted no longer ignored by git check-ignore")
    return 0


if __name__ == "__main__":
    raise SystemExit(_dispatch.run(__file__, cmd_probe, cmd_apply, cmd_verify))
