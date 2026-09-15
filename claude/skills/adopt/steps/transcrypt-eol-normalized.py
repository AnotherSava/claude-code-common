#!/usr/bin/env python3
"""v6 — every filter=crypt line in a repo's .gitattributes ends with `text=auto eol=lf`.

Transcrypt stores base64, which IS text, so git's line-ending conversion applies to
the ciphertext. The openssl build behind it on Windows ends its lines with CRLF where
macOS uses LF, so without a positive normalization rule each clone commits the
ciphertext in its own endings and rewrites the other's on the next round trip — and
because transcrypt derives each file's salt by HMAC over the contents
(learnings/transcrypt-verify-before-commit.md), that is a different blob rather than
the same one, showing up as a whole-file diff on a file nobody opened.

Marking the path `-text` is the tempting wrong answer: it disables normalization,
which is the churn itself. Dropping `-text` without replacing it falls back to each
machine's `core.autocrlf` / `core.eol`, which is the same drift by a quieter route.
Hence the positive spelling, per path.

Three rules shape the code below.

**The check is made with the global attributes file suppressed.** This machine's
~/.gitattributes holds `* text=auto eol=lf`, so an unsuppressed `git check-attr`
answers auto/lf for a broken rule exactly as it does for a correct one — measured on
the one repo in the fleet that fails. No clone is obliged to carry that file.

**A line the parser cannot classify stops the step.** Any line that is not blank, a
comment, an `[attr]` macro, or a plain `pattern attrs...` is printed verbatim and
nothing is written, because a line that cannot be read might be a crypt line and
fixing its neighbours would leave it silently unchanged.

**Only the repo-root file is read.** Transcrypt writes its rules there, and a step
that walked the tree would read every fixture repo shipped inside a steps directory
as part of the host repo's own configuration — this file's own `unreadable-rule`
fixture made the dotfiles repo refuse itself before the scope was narrowed.

    transcrypt-eol-normalized.py probe  <repo-root>              0 applies · 1 no · 2 ask · 3 error
    transcrypt-eol-normalized.py apply  <repo-root> [--dry-run]  0 done · 3 stopped, file intact
    transcrypt-eol-normalized.py verify <repo-root>              0 in shape · 2 unobservable · 3 not

The last line `apply` prints is the record note; the lines above it are the per-rule
evidence behind it. The note is one line and carries no tab, because it becomes a
field in a tab-separated record file.
"""

import os
import re
import subprocess
import sys
from typing import NamedTuple

# sys.path[0] is already this directory when the engine runs the script by path; the insert
# is what lets the authoring gate import this module directly as well.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import _dispatch  # noqa: E402  — path set above

# Emit UTF-8 whatever the console codepage is. This prints .gitattributes lines back
# verbatim, and a comment block carrying an em-dash — several of them do — raises
# rather than prints through Windows' cp1252 default, turning a healthy run into an exit 3.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ATTR_NAME = ".gitattributes"
CRYPT = "filter=crypt"
WANT_TEXT = "text=auto"
WANT_EOL = "eol=lf"
# A path this step invents so `core.attributesfile` points at nothing. Named rather than
# /dev/null because Git Bash on Windows has no such device path to hand git.
NO_ATTRIBUTES = ".adopt-no-such-attributes"

# A pattern this step is willing to rewrite: no quote, no backslash escape, no character
# class. Git accepts all three; none can be turned into a representative path without
# guessing, and a crypt rule that cannot be checked must stop the step rather than be skipped.
PATTERN_RE = re.compile(r"^[^\s\"'\\\[\]!]+$")
ATTR_RE = re.compile(r"^[-!]?[A-Za-z0-9_.][A-Za-z0-9_.-]*(?:=[^\s]+)?$")
MACRO_RE = re.compile(r"^\[attr\][A-Za-z0-9_.-]+$")


class Rule(NamedTuple):
    index: int  # position in the file's line list, which is what apply rewrites
    line_no: int
    pattern: str
    attrs: tuple[str, ...]


class AttrFile(NamedTuple):
    lines: list[str]  # with any CR stripped; `converted` counts how many carried one
    converted: int
    final_newline: bool
    rules: list[Rule]


def read_text(path: str) -> str | None:
    """A file's text, or None when it cannot be read — no caller here may die on that."""
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


def parse_attr_file(raw: str) -> tuple[AttrFile, list[str]]:
    """Classify every line: blank, comment, `[attr]` macro, or pattern followed by attributes.

    A line that is none of those is a problem rather than a skip. The alternative — matching
    the shape this step knows and ignoring the rest — is how a parser ends up verifying only
    its own blind spots, which is idempotence rule 6 and the failure that wrote it.
    """
    lines: list[str] = []
    problems: list[str] = []
    rules: list[Rule] = []
    converted = 0
    for line_no, raw_line in enumerate(raw.split("\n"), 1):
        text = raw_line.rstrip("\r")
        converted += raw_line != text
        lines.append(text)
        stripped = text.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.split()
        head, attrs = fields[0], tuple(fields[1:])
        if not all(ATTR_RE.match(attr) for attr in attrs):
            problems.append(f"line {line_no}: {text}")
            continue
        if MACRO_RE.match(head):
            # An `[attr]NAME a b c` macro definition. Recognised so it cannot read as
            # unclassifiable, and never rewritten: it defines a name, it does not mark a path.
            continue
        if not PATTERN_RE.match(head):
            problems.append(f"line {line_no}: {text}")
            continue
        rules.append(Rule(len(lines) - 1, line_no, head, attrs))
    final_newline = bool(lines) and lines[-1] == ""
    if final_newline:
        lines.pop()
    return AttrFile(lines, converted, final_newline, rules), problems


def read_attr_file(root: str) -> tuple[AttrFile | None, list[str]]:
    """The repo-root .gitattributes, every line of it classified, or None when there is none.

    Root only, deliberately. Transcrypt writes its rules there, all five repos in the fleet
    carry theirs there, and a recursive walk reads a fixture repo shipped inside a steps
    directory as though it were the host repo's own configuration.
    """
    raw = read_text(os.path.join(root, ATTR_NAME))
    if raw is None:
        return None, []
    return parse_attr_file(raw)


def last_of(attrs: tuple[str, ...], name: str) -> str:
    """The effective spelling of one attribute on a rule — the last one wins, as git reads it.

    Taking the first, or merely testing membership, passes a line spelling `text=auto ... -text`,
    where git's answer is the `-text` at the end and the churn this step exists to stop is live.
    """
    hits = [a for a in attrs if a in (name, f"-{name}", f"!{name}") or a.startswith(f"{name}=")]
    return hits[-1] if hits else ""


def conforms(rule: Rule) -> bool:
    return last_of(rule.attrs, "text") == WANT_TEXT and last_of(rule.attrs, "eol") == WANT_EOL


def fault(rule: Rule) -> str:
    """Why one rule is not in the target shape, in the words of its own spelling."""
    parts = []
    for name, want in (("text", WANT_TEXT), ("eol", WANT_EOL)):
        found = last_of(rule.attrs, name)
        if found != want:
            parts.append(f"{found or f'no {name} attribute'} where {want} is required")
    return ", ".join(parts)


def rewritten(rule: Rule) -> str:
    """The rule's line with every text/eol spelling dropped and the required pair appended."""
    keep = [a for a in rule.attrs
            if not (a in ("text", "-text", "!text") or a.startswith("text="))
            and not (a in ("eol", "-eol", "!eol") or a.startswith("eol="))]
    return " ".join([rule.pattern, *keep, WANT_TEXT, WANT_EOL])


def concrete_path(rule: Rule) -> str:
    """A repo-relative path the rule's pattern matches, built from the pattern itself.

    Synthesized rather than looked up among tracked files, so a rule whose file does not exist
    yet is asserted exactly like one whose file does — and so there is no second code path the
    fixtures never reach. A synthesis the rule turns out not to match answers `unspecified` at
    check-attr and fails the step, which is the safe direction.
    """
    body = rule.pattern.lstrip("/")
    body = body.replace("**/", "").replace("/**", "/x").replace("**", "x")
    body = body.replace("*", "x").replace("?", "x")
    return f"{body}x" if body.endswith("/") else body


def git(root: str, *args: str) -> subprocess.CompletedProcess | None:
    """One git command against `root`, with this machine's own attribute files suppressed.

    The suppression is the assertion rather than hygiene: ~/.gitattributes here holds
    `* text=auto eol=lf`, so an unsuppressed check-attr answers auto/lf for a rule carrying
    neither — which is the whole defect, masked. GIT_ATTR_NOSYSTEM disables the system file
    and core.attributesfile is pointed at a path that does not exist.
    """
    suppress = f"core.attributesfile={os.path.join(root, NO_ATTRIBUTES)}".replace("\\", "/")
    try:
        return subprocess.run(["git", "-C", root, "-c", suppress, *args], capture_output=True,
                              encoding="utf-8", errors="replace", timeout=30,
                              env={**os.environ, "GIT_ATTR_NOSYSTEM": "1"})
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def check_attr(root: str, paths: list[str]) -> tuple[dict[str, dict[str, str]], str]:
    """What git says `text` and `eol` resolve to for each path — one fork, whatever the count.

    `-z` rather than the readable rendering: that form is `<path>: <attr>: <value>` and a path
    holding `: ` splits it wrong, while the NUL form has no such ambiguity
    (learnings/git-porcelain-parsing.md makes the same point about status).
    """
    done = git(root, "check-attr", "-z", "text", "eol", "--", *paths)
    if done is None:
        return {}, "git could not be run"
    if done.returncode != 0:
        return {}, (done.stderr or "").strip() or f"git check-attr exited {done.returncode}"
    fields = (done.stdout or "").split("\0")
    answers: dict[str, dict[str, str]] = {}
    for offset in range(0, len(fields) - 2, 3):
        path, attr, value = fields[offset:offset + 3]
        answers.setdefault(path, {})[attr] = value
    return answers, ""


def binary_crypt_files(root: str) -> tuple[list[str], str]:
    """Crypt-marked paths git currently stores as binary, read off the index rather than guessed.

    The `i/` column of `git ls-files --eol` is git's own reading of the staged blob, so this is
    the same judgement the conversion itself would make. One fork for the whole repo, and the
    `:(attr:...)` pathspec does the matching, so no glob has to be re-implemented here.
    """
    done = git(root, "ls-files", "--eol", "-z", "--", ":(attr:filter=crypt)")
    if done is None:
        return [], "git could not be run"
    if done.returncode != 0:
        return [], (done.stderr or "").strip() or f"git ls-files exited {done.returncode}"
    binaries = []
    for entry in (done.stdout or "").split("\0"):
        if not entry.strip():
            continue
        info, _, path = entry.partition("\t")
        if info.split()[0] == "i/-text":
            binaries.append(path)
    return binaries, ""


def assert_resolved(root: str, rules: list[Rule]) -> tuple[bool, list[str]]:
    """Ask git what each rule resolves to, asserted per rule and never on a count.

    One rule answering `unspecified` while another answers `auto` passes any tally that counts
    correct answers against the total, and the unnormalized path is the one that churns.
    """
    answers, failure = check_attr(root, sorted({concrete_path(rule) for rule in rules}))
    if failure:
        return False, [f"git could not be asked what these rules resolve to ({failure})"]
    report, ok = [], True
    for rule in rules:
        path = concrete_path(rule)
        found = answers.get(path, {})
        text, eol = found.get("text", "unspecified"), found.get("eol", "unspecified")
        detail = f"{ATTR_NAME} line {rule.line_no}  {rule.pattern} -> {path} resolves text={text} eol={eol}"
        ok = ok and (text, eol) == ("auto", "lf")
        report.append(f"{'ok            ' if (text, eol) == ('auto', 'lf') else 'NOT RESOLVED  '}{detail}")
    return ok, report


def report_problems(problems: list[str]) -> None:
    """Name every line the parser could not classify, verbatim, and say what was not done."""
    print(f"{ATTR_NAME} holds {len(problems)} line(s) this step cannot classify as a blank, a "
          f"comment, an [attr] macro, or a pattern followed by attributes:")
    for problem in problems:
        print(f"  {problem}")
    print(f"Nothing was written and {ATTR_NAME} is untouched. A quoted pattern, a backslash escape "
          f"or a character class cannot be turned into a path this step can check, and a {CRYPT} "
          f"rule that cannot be checked must not be skipped past. Rewrite those lines by hand, then re-run.")


def no_rules_here(attr_file: AttrFile | None) -> str:
    """The one sentence three subcommands print when nothing here is transcrypt-marked."""
    if attr_file is None:
        return f"there is no {ATTR_NAME} at the root of this repo, so nothing here is transcrypt-marked"
    return (f"{ATTR_NAME} holds {len(attr_file.rules)} rule(s) and none of them is a {CRYPT} line, "
            f"so nothing here is transcrypt-marked")


def binary_question(binaries: list[str]) -> None:
    print(f"{len(binaries)} path(s) marked {CRYPT} are stored by git as binary, so normalizing their "
          f"rule would be a statement about real content rather than about base64:")
    for path in binaries:
        print(f"  {path}")
    print("Is that path meant to be encrypted at all, or has a crypt pattern caught binary by "
          "accident? Read the i/ column of `git ls-files --eol` for it, then either narrow the "
          "pattern and re-run, or record this step n/a with the answer as the note.")


def cmd_probe(root: str) -> int:
    attr_file, problems = read_attr_file(root)
    if problems:
        report_problems(problems)
        return 3
    rules = [rule for rule in attr_file.rules if CRYPT in rule.attrs] if attr_file else []
    if not rules:
        # Positive evidence, per CD4: the file was read and its rules counted. "No crypt rule
        # here" is a fact about what it holds, not an inference from something not being found.
        print(no_rules_here(attr_file))
        return 1
    offending = [rule for rule in rules if not conforms(rule)]
    if not offending:
        print(f"all {len(rules)} {CRYPT} rule(s) in {ATTR_NAME} already carry {WANT_TEXT} {WANT_EOL}")
        return 1
    binaries, failure = binary_crypt_files(root)
    if failure:
        print(f"{len(offending)} {CRYPT} rule(s) are not normalized, but git could not be asked which "
              f"crypt-marked paths it stores as binary ({failure}), and normalizing one of those would "
              f"rewrite real content rather than base64. Answer that first.")
        return 2
    if binaries:
        binary_question(binaries)
        return 2
    for rule in offending:
        print(f"NOT NORMALIZED  {ATTR_NAME} line {rule.line_no}  {rule.pattern} carries {fault(rule)}")
    print(f"{len(offending)} of {len(rules)} {CRYPT} rule(s) do not end with {WANT_TEXT} {WANT_EOL}")
    return 0


def cmd_verify(root: str) -> int:
    """Is this repo in the shape the convention requires — never, was this line ever edited.

    Two assertions, because either alone passes a repo that is wrong: the text of every crypt
    rule, read the way git reads it, and then git's own answer for a path each rule matches with
    the global attributes file suppressed.
    """
    attr_file, problems = read_attr_file(root)
    if problems:
        report_problems(problems)
        return 3
    rules = [rule for rule in attr_file.rules if CRYPT in rule.attrs] if attr_file else []
    if not rules:
        # Never 0. A repo holding no crypt rule satisfies "every crypt rule is normalized"
        # vacuously, and a verify that passes on it cannot tell a normalized repo from one that
        # has never held ciphertext. Exit 2 sends /adopt to probe, which records n/a with a reason.
        print(f"{no_rules_here(attr_file)} — there is no path here whose normalization can be observed")
        return 2
    offending = [rule for rule in rules if not conforms(rule)]
    for rule in offending:
        print(f"NOT NORMALIZED  {ATTR_NAME} line {rule.line_no}  {rule.pattern} carries {fault(rule)}")
    if offending:
        print(f"{len(offending)} of {len(rules)} {CRYPT} rule(s) do not end with {WANT_TEXT} {WANT_EOL}")
        return 3
    ok, report = assert_resolved(root, rules)
    for line in report:
        print(line)
    if not ok:
        # Not exit 2: the rules above were read, so the shape IS observable, and exit 2 would send
        # /adopt on to probe, which answers "already normalized" and files the repo n/a — a repo
        # recorded as never needing a convention its own verify has just refused it (CD1).
        print("the rule text is right and git does not resolve it that way — fix that and re-run "
              "rather than recording a pass nobody made")
        return 3
    print(f"asserted: {len(rules)} {CRYPT} rule(s) in {ATTR_NAME}, each carrying {WANT_TEXT} "
          f"{WANT_EOL} and each resolving to it with the global attributes file suppressed")
    return 0


def write_attr_file(root: str, lines: list[str], final_newline: bool) -> str:
    """Write .gitattributes back. Returns the reason it could not be, or "".

    newline="\\n" so the committed file never shows up as a whole-file line-ending diff between
    the two machines — the same churn this step's rule exists to stop, one level up.
    """
    try:
        with open(os.path.join(root, ATTR_NAME), "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(lines) + ("\n" if final_newline else ""))
    except OSError as exc:
        return f"{ATTR_NAME} could not be written ({exc})"
    return ""


def restore(root: str, attr_file: AttrFile) -> None:
    """Put back exactly what was read, so a failed run leaves the repo as it found it."""
    failed = write_attr_file(root, attr_file.lines, attr_file.final_newline)
    print(failed or f"{ATTR_NAME} has been restored to what it held before this run")


def cmd_apply(root: str, dry_run: bool) -> int:
    attr_file, problems = read_attr_file(root)
    if problems:
        report_problems(problems)
        return 3
    rules = [rule for rule in attr_file.rules if CRYPT in rule.attrs] if attr_file else []
    if not rules:
        print(f"{no_rules_here(attr_file)}, so there is nothing to normalize — whether this repo "
              f"wants transcrypt at all is a question for a human rather than an apply")
        return 3
    offending = [rule for rule in rules if not conforms(rule)]
    others = len(attr_file.rules) - len(rules)
    if not offending:
        # A second apply, or a repo already in shape. Exits 0 rather than crashing, and asserts
        # before saying so: 0 here means the target shape holds, and a claim made without the
        # check behind it is the one thing this system must never record.
        ok, report = assert_resolved(root, rules)
        for line in report:
            print(line)
        if not ok:
            return 3
        print(f"already normalized: {len(rules)} {CRYPT} rule(s) carry {WANT_TEXT} {WANT_EOL}, each "
              f"asserted to resolve that way with the global attributes file suppressed")
        return 0
    binaries, failure = binary_crypt_files(root)
    if failure:
        print(f"git could not be asked which crypt-marked paths it stores as binary ({failure}), and "
              f"normalizing one of those would rewrite real content rather than base64 — nothing was "
              f"written and {ATTR_NAME} is untouched")
        return 3
    if binaries:
        binary_question(binaries)
        print(f"Nothing was written and {ATTR_NAME} is untouched.")
        return 3
    planned = list(attr_file.lines)
    for rule in offending:
        planned[rule.index] = rewritten(rule)
    if dry_run:
        for rule in offending:
            print(f"{ATTR_NAME} line {rule.line_no}")
            print(f"  -  {rule.pattern} {' '.join(rule.attrs)}")
            print(f"  +  {rewritten(rule)}")
        print(f"{len(offending)} of {len(rules)} {CRYPT} rule(s) would gain {WANT_TEXT} {WANT_EOL}; "
              f"{others} other rule(s) and every comment line stay as they are"
              + (f"; {attr_file.converted} line(s) carrying CRLF would be written LF" if attr_file.converted else ""))
        return 0
    failed = write_attr_file(root, planned, attr_file.final_newline)
    if failed:
        print(f"{failed} — {ATTR_NAME} is as it was")
        return 3
    after, trouble = read_attr_file(root)
    results: list[tuple[bool, str]] = []
    same = after is not None and after.lines == planned
    results.append((same, f"{'ok        ' if same else 'MISMATCHED'}  {ATTR_NAME} on disk is the planned file, line for line"))
    fresh = {rule.line_no: rule for rule in after.rules} if after else {}
    for rule in offending:
        now = fresh.get(rule.line_no)
        good = now is not None and now.pattern == rule.pattern and CRYPT in now.attrs and conforms(now)
        spelling = " ".join(now.attrs) if now else "nothing this parser recognises"
        results.append((good, f"{'ok        ' if good else 'NOT FIXED '}  {ATTR_NAME} line {rule.line_no}  {rule.pattern} now carries {spelling}"))
    for _, line in results:
        print(line)
    for problem in trouble:
        print(f"  NOT ASSERTED  {problem}")
    if trouble or any(not good for good, _ in results):
        restore(root, attr_file)
        return 3
    ok, report = assert_resolved(root, [rule for rule in after.rules if CRYPT in rule.attrs])
    for line in report:
        print(line)
    if not ok:
        print(f"git does not resolve the rewritten rules to {WANT_TEXT} {WANT_EOL}")
        restore(root, attr_file)
        return 3
    print(f"{len(offending)} of {len(rules)} {CRYPT} rule(s) in {ATTR_NAME} now carry {WANT_TEXT} "
          f"{WANT_EOL}, each asserted to resolve that way; {others} other rule(s) and every comment "
          f"line left untouched"
          + (f"; {attr_file.converted} line(s) carrying CRLF were written LF" if attr_file.converted else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(_dispatch.run(__file__, cmd_probe, cmd_apply, cmd_verify))
