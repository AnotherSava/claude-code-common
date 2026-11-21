# Comparing against what the other machine pushed, in a fork

To ask "has the other machine pushed commits I lack?", compare against the branch this clone pushes to,
not `@{upstream}`. The two differ in a fork set up triangularly: the branch tracks the third-party
project so a pull brings its changes, and pushes go to the user's own fork.

```
branch.master.remote = upstream    # pull from the third-party project
remote.pushDefault   = origin      # push to the user's fork
```

There, `git log HEAD..@{upstream}` lists every third-party commit not yet merged. Measured 2026-11-20 in
the agterm fork: 242 commits, while `origin/master` equalled `HEAD`. A gate meant to catch the other
machine's pushes reads that as "behind" and stops.

## Resolving the push target

`@{push}` names the push target, but it fails under `push.default=simple` in this setup:

```
$ git rev-parse --abbrev-ref '@{push}'
fatal: cannot resolve 'simple' push to a single destination
```

Either of these works, and both give the same answer as `@{upstream}` in an ordinary clone:

```sh
git -c push.default=current log --oneline HEAD..@{push}     # origin/master in the fork
git for-each-ref --format='%(push:remotename)' "$(git symbolic-ref -q HEAD)"   # origin
```

The `-c push.default=current` form assumes the pushed branch has the local branch's name. That matches what
`simple` does in a triangular setup. A branch never pushed has no `origin/<branch>` yet, so the range fails to
resolve; report that as its own case, never as "up to date".

Every check written as "behind `@{upstream}`" has the same blind spot in such a fork. The `/adopt` gate and
`_pushed_from` in `shared/push.py` handle it; check any other before trusting it in a fork.
