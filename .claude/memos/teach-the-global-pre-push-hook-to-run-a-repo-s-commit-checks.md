---
created: 2026-10-07 04:52:08
---

# Teach the global pre-push hook to run a repo's commit-checks.sh

A repo's `.claude/commit-checks.sh` runs only through `gate_pushed_tree.py`, which the skills call before
committing (`/yolo`, `/wrap-up`, `/adopt`) and `shared/push.py` calls again before pushing. Nothing else runs it. Measured 2026-10-07 in the claude dotfiles repo:
`grep -rn "commit-checks" ~/.git-hooks/` finds nothing, and the repo has no `.github/workflows/` at all,
so `gh run list` is empty unfiltered. A commit made and pushed outside those skills — by hand, by another
tool, or by a session that skipped them — reaches the remote with none of the suite having run.

The asymmetry is what makes this worth doing rather than merely noting. The pre-push hook already covers
that exact bypass path for commit *messages*, and since 2026-10-31 for the privacy scan too: on 2026-10-07 its own comment named "a lone follow-up commit [that]
reaches the push without `/commit` having seen it", and `check-commit-message.py` runs there for any repo
holding a `.claude/conventions` record. So the bypass was recognised and half-closed. The test half was
never examined.

The change: have `~/.git-hooks/pre-push` run `<repo-root>/.claude/commit-checks.sh` when that file exists,
gated the same way the message check is — on the repo holding a `.claude/conventions` record, so a
third-party clone is untouched.

Two costs to weigh before doing it, which is why this is parked rather than done:

- That hook is global and shared by every repo on the machine, so this adds the suite's full runtime to
  every push from a repo that has one. The claude repo's suite measured about 25 seconds on 2026-09-30.
  A per-repo opt-out, or a `--quick` subset, may be the better shape.
- The pre-push hook is a self-gating file: a syntax error or a wrong path there blocks every push,
  including the push that would fix it. `~/.claude/memory/feedback_validate_self_gating_edits.md`
  requires editing a temp copy, running the configured commands against it, and only then replacing the
  real file. The repo's own gate already tests this hook ("pre-push hook: 25 passed, 0 failed"), so a new
  case belongs in that test alongside the change.

Raised in a /wrap-up review on 2026-10-07, after a push whose only verification was the local gate that
`/commit` had already run.
