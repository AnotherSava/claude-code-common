#!/usr/bin/env bash
# What /commit runs before it will draft a commit plan here. This repo commits straight to main and
# has no CI, so nothing else reads a change on its way in.
#
# What makes a defect here expensive is reach rather than severity: everything under `claude/` is
# symlinked into `~/.claude/` on both machines, so a broken hook fires at every session start
# everywhere, and a broken convention reaches every other repo on the machine — its migration editing their
# files, its rule standing in front of their commits.
# Three suites already existed to catch exactly that and nothing ran any of them.
#
# Deliberately absent: a linter. There is no lint config in this repo and adopting one is its own
# decision with its own baseline to triage, not something to smuggle in behind a commit gate.
# The ~/.claude symlinks are asserted here without a line of their own: the "Conventions — this repo"
# run below includes the universal rule install-links-present, which imports `check-install.py`'s
# LINKS, so every link listed there is checked at every commit, as it is at session start.
#
# Prerequisite is `python3` on PATH. Its absence fails rather than skips: a check that cannot tell
# "passed" from "never ran" turns an open problem into a closed-looking one.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 2

status=0

# Buffer each suite and print its detail only when it fails. The authoring gate alone prints a line
# per assertion, and a wall of `ok` at every commit is how a gate stops being read — but a silent
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

# The authoring gate for the conventions. Its failure is the one here that reaches other people's
# repositories: a version whose README is missing a section is one `/adopt` walks everywhere, a rule
# named by no version or a version naming a rule with no file, and above all a rule that returns a
# clean list for a tree it should have refused — each of those ships from here into every repo's
# commit gate. Every rule is exercised against a conforming and a violating tree the test builds
# itself, which is why it is worth the seconds it takes.
run "Conventions — authoring gate" python3 claude/conventions/tests.py

# The checker every repo's commit gate runs, pointed at this one. A repo that authors the rules is
# also a repo they apply to, and exempting it would be the one place a rule could ship that its own
# author's tree fails. Which rules run here is read off this repo's adopted number, exactly as it is
# anywhere else.
run "Conventions — this repo" python3 claude/conventions/check.py .

# Two silent data-loss bugs shipped in memos.py within a day of each other, both exiting 0 with a
# plausible line. That suite pins the cases where a string comparison and a directory entry
# disagree, which is the class neither bug announced.
run "memos.py" python3 claude/tests/memos.py

# The install blocks in README.md against check-install.py's lists. Measured 2026-09-16: the
# `~/.claude/conventions` link was in both blocks and in neither list, so it existed on neither
# machine and the session-start check called the install clean on both — every documented
# conventions command failed while nothing anywhere said why. Three copies of one contract, paired
# by hand until this ran.
run "install links" python3 claude/tests/install-links.py

# Every .py here against the oldest interpreter a caller can hand it. macOS ships 3.9 as
# /usr/bin/python3, and a non-interactive ssh resolves to it rather than to the Homebrew 3.14 the
# same machine uses interactively — so nine `tuple[...] | None` annotations under
# claude/conventions/ left the engine unimportable over there: fifteen repos reported as having
# nothing to adopt, no repo's gate able to run, every one of those files correct on 3.10 and up.
run "python baseline" python3 claude/tests/python-baseline.py

# The co-tenancy linter three project repos call from this one copy. A regression here is silent in
# the worst way the fleet knows: the arrangement it guards already cost 41 hours of a commercial
# site serving a neighbour's application with every conventional check green.
run "ingress-lint.py" python3 claude/tests/ingress-lint.py

# The port allocator, and the registry it hands out from. Two claims on one number is a port given to two
# projects, and the registry is edited by hand as often as by the allocator — so the committed file is run
# through its own checker here, not only the code that writes it. The suite stubs the live probe; the
# `check` below is what reads this machine.
run "ports.py" python3 claude/tests/ports.py
run "ports registry" python3 claude/skills/ports/scripts/ports.py check

# The message checker the pre-push hook below calls in every repo that has adopted these
# conventions, so a false positive there stops real work while a false negative is the hole the
# checker exists to close.
run "commit messages" python3 claude/tests/check-commit-message.py

# The sandbox a sub-skill reviews instead of the user's tree. A change set it fails to carry in is a
# review that reports success over files it never saw.
run "worktree sandbox" python3 claude/tests/worktree-sandbox.py

# The global pre-push hook, which every push on both machines runs and which nothing else tests. A
# review of one change to it found three defects, each of which let a push through that it existed
# to stop or stopped one it had no reason to. Most cases are a real push to a bare repo on disk, and
# the whole run is sealed from this machine's git config and signing key.
run "pre-push hook" bash claude/tests/pre-push-hook.sh

# The global pre-commit hook, the last thing between a transcrypt secret and a plaintext commit. The
# case it most needs to cover is a clone not yet unlocked, where git ignores the crypt filter and a
# secret rewritten there stages as it reads — which a check gated on transcrypt being set up misses.
# Each case runs in a sealed scratch repo, and a refusal counts only when it carries the refusing
# check's own words.
run "pre-commit hook" bash claude/tests/pre-commit-hook.sh

# The hook that files an approved plan into the repo, unattended at every approval on both machines.
# Both of its failures are quiet: a plan filed into a fork or someone else's clone sits among their
# design docs until a commit carries it upstream, and a plan moved rather than copied is gone once
# that working tree is cleaned.
run "plan archive" python3 claude/tests/plan-archive.py

# The saved workflow automated review loops run through. What it guarantees is decided in plain code — which
# verified findings get code, that a quiet round ends the loop, that it never passes two rounds — and a loop
# without it coded 125 findings in one day, 85 of them rated low. Needs node; its absence fails rather than skips.
run "review-and-fix workflow" node claude/tests/review-and-fix.mjs

# The backstop that warns when an inline workflow fixes findings without rating realism. Too quiet and the next
# such loop runs unnoticed; too loud on review-only workflows and the warning stops being read.
run "workflow realism hook" python3 claude/tests/workflow-realism.py

# The PreToolUse guards that read Bash commands, and the shared module that finds command position
# for them. A guard that refuses too little leaks a secret into the transcript; one that refuses too
# much blocks writing about the thing it guards, which is how the Doppler guard's first version
# failed three times in twenty minutes.
run "bash guards" python3 claude/tests/bash-guards.py

# The skills the push rule in settings.json clears to push, against the notice each one owes the other
# machine. The permission gate already refuses a push from a skill that list does not name, so the hole
# is a skill added to the list with no notice wired — which is how `/release` pushed a version bump to
# `tauri-dashboard`'s main for a release with nothing sent, leaving the Windows clone behind and nothing
# reporting it.
run "push notifies peer" python3 claude/tests/push-notifies-peer.py

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
