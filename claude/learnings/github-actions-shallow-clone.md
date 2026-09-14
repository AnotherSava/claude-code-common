# A CI check that reads git history fails on the default shallow clone

`actions/checkout` clones with `fetch-depth: 1` unless told otherwise. The working
tree is complete, so anything that only reads *files* is fine — which is most
things, and why this stays hidden. Anything that asks git about **history** gets a
repository containing exactly one commit.

Measured case: a documentation gate resolved each screenshot's `verifiedAt` field —
a commit sha recorded when that image was last examined — with `git cat-file -e`.
Every entry reported `is not a commit in this repository`, and the workflow failed
on three consecutive pushes while the identical script passed locally on two
different machines.

```yaml
      - uses: actions/checkout@v5
        with:
          fetch-depth: 0      # full history: the script resolves shas
```

Things that need this beyond sha resolution: `git describe`, `git log` over more
than the tip, `git merge-base`, commit counts, "changed since the last tag", and
any blame- or age-derived value.

## Fix the clone, not the checker

The tempting alternative is to make the script shrug when a sha will not resolve.
Do not: the only environment where it cannot resolve is the one where the check
runs unattended, so the "fix" disarms it exactly there and leaves it working only
on machines that were never the risk. Widen the clone instead. `fetch-depth: 0`
costs a full fetch — real on a large repo, irrelevant on most — and a middle value
works when the history depth needed is bounded and known.

## The class this belongs to

**A CI-only failure is structurally invisible from a developer machine.** It lives
in the *difference* between the two environments — clone depth, runner OS, an
unset variable, a tool the image lacks — and a local run cannot sample that
difference by construction. So "it passes locally" is not evidence about CI, and a
local gate reported as if it were the build is a category error rather than
optimism. Two habits follow:

- Watch the run after pushing rather than inferring from the local gate. A red
  build noticed hours later is the same defect as one nobody watched for.
- When a job fails and the same command passes locally, suspect the environment
  difference *first* rather than the script. The script is the thing both
  environments share, so it is the least likely difference.
