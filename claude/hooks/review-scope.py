#!/usr/bin/env python3
"""
review-scope.py — widen every `review-auto` run to the commits pushed since the last review.

A PreToolUse hook on the Workflow tool. When the call names the saved `review-auto` workflow, it reads the
repo's review bookmark (`claude/scripts/review_scope.py`), appends the unreviewed commits to `args.scope`, and
passes `args.review_bookmark` — the base and the tree at launch — so the workflow's last step can record what it
covered. The rewrite goes back as `updatedInput`, so the model writing the call cannot leave the range out.

The repo is `args.repo` when the call names one, else the project directory. A non-git directory, an unreadable
args object, or any other workflow passes through untouched. When no base can be trusted (origin unreadable,
history rewritten past the bookmark) the scope says so and no `review_bookmark` is passed, so that review can never
be recorded as covering a range it did not see. The script never raises and exits 0 on every path.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import review_scope  # noqa: E402 — needs the sys.path line above


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    if not isinstance(tool_input, dict) or tool_input.get("name") != review_scope.WORKFLOW:
        return 0
    args = tool_input.get("args")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return 0
    if not isinstance(args, dict) or not isinstance(args.get("scope"), str):
        return 0

    start = args.get("repo") if isinstance(args.get("repo"), str) else (os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd())
    repo = review_scope.toplevel(start)
    if repo is None:
        return 0
    # A failure here must not pass silently: the review would run on the model's scope alone and look widened.
    try:
        found = review_scope.plan(repo)
        tree = review_scope.worktree_tree(repo) if found["base"] else None
    except Exception as error:
        # The rewrite still goes back, without a bookmark: one the caller wrote would let this unwidened review be recorded.
        unrecorded = {key: value for key, value in args.items() if key != "review_bookmark"}
        sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": {**tool_input, "args": unrecorded}, "additionalContext": (
            f"The review-scope hook failed ({error}), so this review covers only the scope its call names and will not be "
            f"recorded. Commits pushed since the last review are not in it; tell the user.")}}))
        return 0
    widened = {**args, "scope": args["scope"] + review_scope.scope_text(found)}
    widened.pop("review_bookmark", None)
    if tree:
        widened["review_bookmark"] = {"repo": repo, "base": found["base"], "tree": tree}
    note = (f"The review-scope hook widened this review: {len(found['commits'])} commit(s) since the last review were added to its scope."
            if found["commits"] else None)
    if found["problem"]:
        note = f"The review-scope hook could not widen this review. {found['problem']} Tell the user, and ask which base to review from."
    output: dict = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": {**tool_input, "args": widened}}}
    if note:
        output["hookSpecificOutput"]["additionalContext"] = note
    sys.stdout.write(json.dumps(output))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
