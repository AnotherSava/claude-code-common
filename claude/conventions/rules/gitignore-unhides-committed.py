"""No ignore rule hides a file the conventions require this repo to commit.

Five paths in this system are meant to be in the repo: the project settings, the committed memory
directory, the memo backlog, the convention record `/adopt` writes, and the transcrypt-encrypted
publish config. An ignore rule that covers any of them — or anything *inside* the two that are
directories — makes the file silently never stage: `git add` says nothing, `git status` shows
nothing, and the loss surfaces on the other machine as a file that was never there. That is the
failure `config/publish.env` was taken out of the global excludes to end.

The verdict is taken from `git check-ignore`, never from the text of a `.gitignore`, so a pattern
that reaches one of these paths by a route nobody predicted is still caught. The traps in doing
that correctly — why `-v` is the wrong form to read a verdict from, why `--no-index` belongs here,
why `-z` — are in `_git.py` beside the calls they govern.

The question asked is about the *rules*, which is why this uses the `--no-index` form rather than
the index-consulting one: a repo that once force-added a file it excludes must not read as clean
while the rule still hides every new file beside it.

A hide from the global excludes file or from `.git/info/exclude` counts too, and the line names the
source so a reader can see which file to edit. Those two do not travel, so the same tree answers
differently on the other machine — which is exactly the shape this rule exists to make loud rather
than let a repo carry silently.
"""

import _git

# Every path the conventions require committed. Directories carry a trailing slash so git is told
# what kind of thing it is being asked about; the two file paths are the ones a rule most often
# catches by accident, since each sits beside a sibling that genuinely is machine-local —
# `.claude/conventions.local` beside the record, `config/deploy.env` beside the publish config.
REQUIRED = (".claude/settings.json", ".claude/memory/", ".claude/memos/",
            ".claude/conventions", "config/publish.env")

# Asking about a directory answers only whether *the directory* is ignored, and a rule reaching its
# contents instead — `.claude/memos/*.md`, `.claude/memory/project_*.md` — is invisible to that
# question. Measured on a scratch repo carrying both: every memo and every project-memory file was
# hidden while the question asked of the directories alone came back clean. So the files git
# currently hides inside a required directory are asked about by name alongside the directory.
REQUIRED_DIRS = tuple(path for path in REQUIRED if path.endswith("/"))


def covering_dir(path: str) -> str | None:
    """Which required directory this path sits inside, if any."""
    return next((base for base in REQUIRED_DIRS if path.startswith(base) and path != base), None)


def asked_about(root: str) -> list[str]:
    """The required paths, plus whatever git already hides inside a required directory.

    The second half is what a static list cannot hold: a rule naming the contents of a directory
    rather than the directory is a different question from the one the list asks, and no enumeration
    of filenames could anticipate the next memo. Asking git which paths it hides today and keeping
    the ones under a required directory turns that into an answer read off the tool.
    """
    inside = {path for path in _git.ignored_on_disk(root) if covering_dir(path)}
    return list(REQUIRED) + sorted(inside - set(REQUIRED))


def check(root: str) -> list[str]:
    """Every required path this repo hides, one line each. Empty list means none of them is hidden.

    Non-vacuous by construction: the answer is the output of a command that has to run inside a work
    tree, so an empty directory cannot produce a clean result. A repo owning no `.gitignore` at all
    holds, and correctly — the shape asserted is "nothing hides these paths", not "a file was
    edited".
    """
    asked = asked_about(root)
    hidden = _git.ignored(root, asked)
    rules = _git.rules_for(root, sorted(hidden))
    lines: list[str] = []
    for path in sorted(hidden):
        rule = rules.get(path)
        # A path git hid and then named no rule for is still hidden — the plain form settled that —
        # so it is reported as a violation rather than swallowed for want of a line to point at.
        where = f"{rule.source}:{rule.line_no} {rule.pattern}" if rule else "a rule git would not name"
        lines.append(f"{path} is ignored ({where}) — a file this repo is meant to commit would "
                     f"silently never stage")
    return lines
