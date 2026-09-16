"""Every filter=crypt line in a repo's .gitattributes ends with `text=auto eol=lf`.

Transcrypt stores base64, which IS text, so git's line-ending conversion applies to the ciphertext.
The openssl build behind it on Windows ends its lines with CRLF where macOS uses LF, so without a
positive normalization rule each clone commits the ciphertext in its own endings and rewrites the
other's on the next round trip — and because transcrypt derives each file's salt by HMAC over the
contents (learnings/transcrypt-verify-before-commit.md), that is a different blob rather than the
same one, showing up as a whole-file diff on a file nobody opened.

Marking the path `-text` is the tempting wrong answer: it disables normalization, which is the
churn itself. Dropping `-text` without replacing it falls back to each machine's `core.autocrlf` /
`core.eol`, which is the same drift by a quieter route. Hence the positive spelling, per path.

Three things shape the code below.

**The question is put to git with this machine's attribute files suppressed.** The `~/.gitattributes`
here holds `* text=auto eol=lf`, so an unsuppressed `git check-attr` answers auto/lf for a broken
rule exactly as it does for a correct one — measured on the one repo in the fleet that failed. No
clone is obliged to carry that file.

**A line the parser cannot classify is a finding, not a skip.** Any line that is not blank, a
comment, an `[attr]` macro, or a plain `pattern attrs...` is reported verbatim, because a line that
cannot be read might itself be a crypt rule and calling its neighbours sound would assert something
about a file nobody read.

**Only the repo-root file is read.** Transcrypt writes its rules there, and a walk of the tree would
read a `.gitattributes` belonging to something vendored or generated as part of this repo's own
configuration.

A repo whose root `.gitattributes` holds no crypt rule — or that has none at all — holds vacuously.
That is the right answer for a check a commit gate runs: there is no ciphertext here whose
normalization could drift, and refusing instead would fail the gate of every repo that has never
used transcrypt.
"""

import os
import re
import subprocess
from typing import NamedTuple

import _git

ATTR_NAME = ".gitattributes"
CRYPT = "filter=crypt"
WANT_TEXT = "text=auto"
WANT_EOL = "eol=lf"
# A path named so `core.attributesfile` points at nothing. Named rather than /dev/null because Git
# Bash on Windows has no such device path to hand git.
NO_ATTRIBUTES = ".conventions-no-such-attributes"

# A pattern that can be turned into a representative path: no quote, no backslash escape, no
# character class. Git accepts all three; none can be synthesized without guessing, and a crypt rule
# that cannot be checked must be reported rather than skipped.
PATTERN_RE = re.compile(r"^[^\s\"'\\\[\]!]+$")
ATTR_RE = re.compile(r"^[-!]?[A-Za-z0-9_.][A-Za-z0-9_.-]*(?:=[^\s]+)?$")
MACRO_RE = re.compile(r"^\[attr\][A-Za-z0-9_.-]+$")


class Unreadable(Exception):
    """The attributes file is there and would not read, so what it marks was never established.

    Distinct from absence, which is an answer: no `.gitattributes` means nothing here is
    transcrypt-marked, while one that will not open as text means every rule in it is unknown.
    """


class Rule(NamedTuple):
    line_no: int
    pattern: str
    attrs: tuple[str, ...]


def parse_attr_file(raw: str) -> tuple[list[Rule], list[str]]:
    """Classify every line: blank, comment, `[attr]` macro, or pattern followed by attributes.

    A line that is none of those comes back among the problems rather than being dropped. The
    alternative — matching the shape this parser knows and ignoring the rest — is how a check ends
    up asserting only its own blind spots.
    """
    rules: list[Rule] = []
    problems: list[str] = []
    for line_no, raw_line in enumerate(raw.split("\n"), 1):
        # The CR goes before the split into fields, so a CRLF file does not arrive with a stray
        # carriage return glued to its last attribute and read as a line nobody could classify.
        text = raw_line.rstrip("\r")
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
            # unclassifiable, and never treated as a rule: it defines a name, it does not mark a path.
            continue
        if not PATTERN_RE.match(head):
            problems.append(f"line {line_no}: {text}")
            continue
        rules.append(Rule(line_no, head, attrs))
    return rules, problems


def read_attr_file(root: str) -> tuple[list[Rule], list[str]]:
    """The repo-root .gitattributes, classified. Empty when there is none; raises when it will not read.

    Root only, deliberately. Transcrypt writes its rules there, and every repo in the fleet carrying
    ciphertext keeps them there.
    """
    try:
        with open(os.path.join(root, ATTR_NAME), encoding="utf-8") as handle:
            raw = handle.read()
    except FileNotFoundError:
        return [], []
    except (OSError, UnicodeDecodeError) as exc:
        raise Unreadable(f"{ATTR_NAME} is there and could not be read as UTF-8 text ({exc})") from exc
    return parse_attr_file(raw)


def last_of(attrs: tuple[str, ...], name: str) -> str:
    """The effective spelling of one attribute on a rule — the last one wins, as git reads it.

    Taking the first, or merely testing membership, passes a line spelling `text=auto ... -text`,
    where git's answer is the `-text` at the end and the churn this rule exists to stop is live.
    """
    hits = [attr for attr in attrs
            if attr in (name, f"-{name}", f"!{name}") or attr.startswith(f"{name}=")]
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


def concrete_path(rule: Rule) -> str:
    """A repo-relative path the rule's pattern matches, built from the pattern itself.

    Synthesized rather than looked up among tracked files, so a rule whose file does not exist yet is
    asserted exactly like one whose file does, and so there is no second code path. A synthesis the
    rule turns out not to match answers `unspecified` at check-attr and is reported, which is the
    safe direction.
    """
    body = rule.pattern.lstrip("/")
    body = body.replace("**/", "").replace("/**", "/x").replace("**", "x")
    body = body.replace("*", "x").replace("?", "x")
    return f"{body}x" if body.endswith("/") else body


def check_attr(root: str, paths: list[str]) -> dict[str, dict[str, str]]:
    """What git says `text` and `eol` resolve to for each path — one fork, whatever the count.

    Run through subprocess here rather than through `_git.git`, because half the suppression is an
    environment variable: `GIT_ATTR_NOSYSTEM` is the only way to take the system attributes file out
    of the answer, and the shared helper passes no environment. The other half, `core.attributesfile`
    pointed at a path that does not exist, drops this machine's `~/.gitattributes`. Without both, a
    rule carrying neither attribute answers auto/lf anyway and the defect is masked.

    Asked with `-z` rather than the readable rendering: that form is `<path>: <attr>: <value>` and a
    path holding `: ` splits it wrong, while the NUL form has no such ambiguity
    (learnings/git-porcelain-parsing.md makes the same point about status).
    """
    suppress = f"core.attributesfile={os.path.join(root, NO_ATTRIBUTES)}".replace("\\", "/")
    command = ["git", "-C", root, "-c", suppress, "check-attr", "-z", "text", "eol", "--", *paths]
    try:
        done = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace",
                              timeout=_git.GIT_TIMEOUT, env={**os.environ, "GIT_ATTR_NOSYSTEM": "1"})
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise _git.GitRefused(f"git check-attr could not be run in {os.path.basename(root)} ({exc})") from exc
    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip().splitlines()
        raise _git.GitRefused(f"git check-attr exited {done.returncode} rather than saying what these "
                              f"rules resolve to{' — ' + detail[0] if detail else ''}")
    fields = (done.stdout or "").split("\0")
    answers: dict[str, dict[str, str]] = {}
    for offset in range(0, len(fields) - 2, 3):
        path, attr, value = fields[offset:offset + 3]
        answers.setdefault(path, {})[attr] = value
    return answers


def unresolved(root: str, rules: list[Rule]) -> list[str]:
    """Every crypt rule git does not resolve to auto/lf, asked per rule and never on a count.

    One rule answering `unspecified` while another answers `auto` passes any tally that counts
    correct answers against the total, and the unnormalized path is the one that churns.
    """
    answers = check_attr(root, sorted({concrete_path(rule) for rule in rules}))
    found: list[str] = []
    for rule in rules:
        path = concrete_path(rule)
        resolved = answers.get(path, {})
        text, eol = resolved.get("text", "unspecified"), resolved.get("eol", "unspecified")
        if (text, eol) != ("auto", "lf"):
            found.append(f"{ATTR_NAME} line {rule.line_no}  {rule.pattern} -> {path} resolves text={text} "
                         f"eol={eol} with the global attributes file suppressed, whatever its own text says")
    return found


def check(root: str) -> list[str]:
    """Every crypt rule that is not normalized, one line each."""
    rules, problems = read_attr_file(root)
    if problems:
        return [f"{ATTR_NAME} {problem}  — this rule cannot classify that as a blank, a comment, an "
                f"[attr] macro, or a pattern followed by attributes, so a {CRYPT} line hiding in it "
                f"would go unchecked" for problem in problems]
    crypt = [rule for rule in rules if CRYPT in rule.attrs]
    if not crypt:
        # Vacuous, and the right answer: nothing here is transcrypt-marked, so no ciphertext can
        # drift. Asking git about an empty path list would also be a fork with no question in it.
        return []
    offending = [rule for rule in crypt if not conforms(rule)]
    if offending:
        # Git is asked nothing while the text is wrong: a rule spelling neither attribute will not
        # resolve either, and reporting both would make one defect read as two.
        return [f"{ATTR_NAME} line {rule.line_no}  {rule.pattern} carries {fault(rule)}"
                for rule in offending]
    # Two assertions, because either alone passes a repo that is wrong: the text of every crypt rule,
    # read the way git reads it, and then git's own answer for a path each rule matches.
    return unresolved(root, crypt)
