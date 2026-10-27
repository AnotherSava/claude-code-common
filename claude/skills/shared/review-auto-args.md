# Building the review-auto workflow's args

The `review-auto` workflow refuses to start without a `scope` string and a non-empty `lenses` array, and nothing
fills them in for you: a bare `/review-auto` or `/review-auto cap 6` reaches the workflow with whatever object the
calling session builds. Build the whole object from the conversation before calling
`Workflow({name: "review-auto", args})`.

- `scope`: what to review, by default "the uncommitted diff in <repo>". The review scope hook adds the commits pushed
  since the last review, so do not list them.
- `lenses`: one `{key, prompt}` per concern the user named or the change plainly needs. With nothing named, cover
  correctness, duplicated logic, and documentation that the change made stale.
- `context`: every decision the user has settled about this change, and every finding an earlier round dropped or the
  user declined, each with its reason, so neither is reported again as new.
- `gate`: the command that actually gates a commit here — `bash .claude/commit-checks.sh` when that file exists,
  otherwise the project's own build, lint and test scripts.
- `fix`: `true` unless the review is meant to be read-only; `/review-manual` always passes `false`.
- `rounds`: a number the user typed in plain words — "cap 6", "rounds 6", "6 rounds" — is the round cap. Leave it out
  otherwise; the workflow defaults to 3.
- `repo`: only when the repo is not the working directory.
