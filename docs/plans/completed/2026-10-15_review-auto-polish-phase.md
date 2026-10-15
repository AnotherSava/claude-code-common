# Polish inside review-auto

## Goal

`/commit` runs `/clean-code` (step 3) and `/docs-relevance` (step 4) after `review-auto` has converged, so code changes after the last review and nothing reviews those changes. Move both into the workflow as a final phase, keeping the order review → polish, and make the polish itself reviewed or reverted. `/commit` then finds nothing to change on a reviewed tree.

Screenshots, `/reflect`, the confidentiality scan and the commit gate stay in `/commit`.

## Design

### 1. Polish phase in `claude/workflows/review-auto.js`

Runs only in fix mode (`fix !== false`), and only after the loop is quiet (a round found nothing to fix). `/review-manual` (fix: false) is unaffected.

1. Snapshot the tree: `git stash create` gives a commit of the working tree without touching it; an empty output means a clean tree, and HEAD is the snapshot.
2. One agent applies `/clean-code`'s rules to the scope, non-interactively (see open decision A).
3. One agent applies `/docs-relevance`'s text steps (README, docs, CLAUDE.md, comments) to the code as polished, skipping its screenshot step. It follows the skill body directly rather than invoking the fork, since a workflow agent cannot wait on a background fork.
4. Run the gate. On a non-zero exit, restore the polished files from the snapshot (`git restore --source=<snapshot> -- <paths>`) and record the polish as reverted with the gate tail. Polish is optional, so it is dropped, never repaired.
5. One review round, bug lenses only, scoped to the polish diff (`git diff <snapshot>`). A finding that verifies true reverts the hunks behind it from the snapshot rather than sending them to the fixer, so no unreviewed code is written after this round.
6. Every polish edit, reverted or kept, becomes a row in the triage table with disposition `polish` / `polish-reverted`, replacing `/clean-code`'s approval prompt.

New phases in `meta.phases`: `Polish` and `Polish review`, between `Fix` and `Bookmark`.

### 2. Bookmark records the polish

- `bookmarkGap()` gains: polish did not complete (an agent returned nothing, or the polish review left an unverified finding).
- `review_scope.py mark` takes `--polished`; the record becomes `{base, tree, polished}`.
- New `review_scope.py status` prints whether the working tree equals a recorded tree and whether it was polished, for `change_scope.py` to read.

### 3. `/commit` skips what the workflow already did

- `change_scope.py` asks `review_scope.py` (imported, not shelled) whether the current tree is the recorded polished one. If so, both verdicts are `SKIP` with reason "review-auto polished this tree"; otherwise unchanged behaviour. An unreadable record is `RUN`, never `SKIP`.
- Split `/docs-relevance`'s step 4 (Check documentation screenshots) into a new skill, `screenshot-relevance`, carrying its three Context probes (doc image files, the manifest, repository privacy), the project-guidelines opt-out, and the upstream-owned rule. It keeps the detection/capture boundary with `screenshot`, which it hands captures to as step 4 does now. `/docs-relevance` becomes text only; the cross-references in `screenshot`'s description and body move to the new skill.
- `change_scope.py` prints a third verdict, `screenshot-relevance`, which a polished tree does not skip; `/commit` step 4 runs it after the text pass. It SKIPs when the repo has no doc images and the diff touches no UI source.

### 4. `/clean-code` additions

- **Complexity and over-engineering audit** (new step after duplication): unnecessary nesting, nested ternaries, abstractions with a single caller and no second in sight, generality nobody asked for, comments that restate the code. Source: Google's "What to look for in a code review" (Complexity) and Anthropic's `code-simplifier` agent.
- **Deterministic tools first** in the dead-code and import steps: run the project's own configured tool (ruff `F401`/`F841`, knip, vulture, `tsc --noUnusedLocals`) when present and use the LLM pass for what they cannot see (cascades across files, test-only callers). Never install one unasked; offering it falls under Best-Practice Adoption.
- **Non-interactive mode** for the workflow, per open decision A.

### 5. `/docs-relevance` addition

- In the source-comment pass: a `TODO`/`FIXME` in a touched file whose described work is now done gets removed or rewritten. Source: Anthropic's `comment-analyzer`.

### 6. Tests and docs

- `claude/tests/review-auto.mjs`: polish runs only when quiet and in fix mode; gate failure reverts; a verified polish finding reverts its hunks; bookmark gap on an incomplete polish. Break each to prove the test.
- `claude/tests/review-scope.py`: `mark --polished`, `status`.
- A test for `change_scope.py`'s new SKIP and its RUN on an unreadable record.
- Update `claude/learnings/adversarial-review-workflows.md`, the `review-auto` and `/commit` skill text, and `meta.whenToUse`.

## Open decisions

A. **What polish may apply unattended — decided 2026-10-15: everything** `/clean-code` finds, relying on the gate and the polish review round; each edit is a row in the triage table. `/clean-code` run by hand keeps its approval prompts.

B. **"No UI source" for the screenshot SKIP.** `change_scope.py` has no notion of UI files today; either the project's screenshot manifest names the sources each shot depends on, or the verdict is RUN whenever doc images exist.

C. **Cost.** Polish adds two agents, a gate run and a review round to every fix-mode run that converges. Measure one run before and after on a real change set.

## As built (2026-10-15)

Where the implementation departs from the design above:

- **The snapshot is `review_scope.py snapshot`**, the same scratch-index tree the bookmark records, because `git stash create` leaves untracked files out.
- **A confirmed defect in the polish reverts the whole polish**, not its hunks. Polish edits span files (a consolidated duplicate), so a partial revert can break the rest, and only a full revert returns the tree to one a snapshot comparison can prove reviewed. The revert names only the files the polish passes reported; a tree still differing afterwards is reported and left unrecorded, so a peer's concurrent write is never reverted.
- **A polish pass that returns nothing is not reverted**, since what it edited is unknown; the run is left unrecorded and says its edits are unreviewed.
- **`/docs-relevance` keeps its sandbox inside the workflow**: the polish agent follows the skill as written and applies the patch it hands back.
- **The `/commit` skip compares paths, not trees.** There is no `review_scope.py status`; `change_scope.py` imports `polished_since`, which lists what changed since the polished tree. `/reflect` writing a memory afterwards still skips both passes, a documentation path re-runs `/docs-relevance` alone, and a code path re-runs both.
- **A polish edit's row keeps disposition `polish` either way**; a reverted one says so in its outcome (`reverted: <reason>`) rather than in a `polish-reverted` disposition.
- **Open decision B was settled as RUN whenever the docs hold images**; no notion of UI source was added.
- **The two forked skills share their sandbox procedure** through `claude/skills/shared/forked-sandbox.md`.
