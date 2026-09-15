#!/usr/bin/env bash
# What /commit runs before it will draft a commit plan here. This repo commits straight to main and
# has no CI, so nothing else reads a change on its way in.
#
# What makes a defect here expensive is reach rather than severity: everything under `claude/` is
# symlinked into `~/.claude/` on both machines, so a broken hook fires at every session start
# everywhere, and a broken adoption step runs against fifteen other repos and edits their files.
# Three suites already existed to catch exactly that and nothing ran any of them.
#
# Deliberately absent: a linter. There is no lint config in this repo and adopting one is its own
# decision with its own baseline to triage, not something to smuggle in behind a commit gate.
# Also absent: any check of the ~/.claude symlinks. `check-install.py` owns that, it runs at every
# session start already, and its answer is about this machine rather than about the change set.
#
# Prerequisite is `python3` on PATH. Its absence fails rather than skips: a check that cannot tell
# "passed" from "never ran" turns an open problem into a closed-looking one.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 2

status=0

# Buffer each suite and print its detail only when it fails. The authoring gate alone prints 227
# assertion lines, and a wall of `ok` at every commit is how a gate stops being read — but a silent
# pass is the other failure, so the tally line always shows.
run() {
  local label="$1" out
  shift
  out="$(mktemp)"
  if "$@" >"$out" 2>&1; then
    echo "==> $label — $(tail -n 1 "$out")"
  else
    echo "==> $label — FAILED"
    cat "$out"
    status=1
  fi
  rm -f "$out"
}

# The authoring gate for the convention steps. It is the only one of the three whose failure would
# reach other people's repositories: a step that ships with a `verify` passing vacuously, an `apply`
# that is not idempotent, or a parser that skips a line it cannot classify gets run by `/adopt` in
# fifteen repos and edits their files. It exercises every step against its own fixtures, which is
# why it is worth the seconds it takes.
run "Convention steps — authoring gate" python3 claude/skills/adopt/conventions.py selftest

# Two silent data-loss bugs shipped in memos.py within a day of each other, both exiting 0 with a
# plausible line. That suite pins the cases where a string comparison and a directory entry
# disagree, which is the class neither bug announced.
run "memos.py" python3 claude/tests/memos.py

# The co-tenancy linter three project repos call from this one copy. A regression here is silent in
# the worst way the fleet knows: the arrangement it guards already cost 41 hours of a commercial
# site serving a neighbour's application with every conventional check green.
run "ingress-lint.py" python3 claude/tests/ingress-lint.py

# The global memory index. `claude/memory/MEMORY.md` is authored; CLAUDE.md's list is generated from
# it, and CLAUDE.md is injected into every session on both machines. Hand-maintaining the two is what
# this replaced: they had drifted to 68 entries against 141, sharing 16, and nothing said so. The
# check also asserts coverage both ways, because a memory indexed nowhere is one nothing can surface
# and an entry whose file is gone is a link to nothing — neither shows up in `git status`.
run "memory index" python3 claude/scripts/render-memory-index.py --check

# Reported, never fatal. A skill git is ignoring is a real problem — the only copy stays on the
# machine that made it — but it is a state of the repo rather than a defect in the change set, and
# blocking an unrelated commit on it would train the gate away.
echo "==> Skill tracking (report only)"
bash claude/scripts/audit-skill-tracking.sh || true

exit "$status"
