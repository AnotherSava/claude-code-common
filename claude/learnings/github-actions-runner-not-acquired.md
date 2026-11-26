# GitHub Actions: a job cancelled because no runner picked it up

A workflow run can show **failure** without any of your code having run. The usual case is a hosted macOS
runner that GitHub could not supply in time.

## How to recognise it

- One job in the matrix is `cancelled`, after about 15 minutes, and the run's conclusion is `failure`.
- The job lists **no steps**. `gh run view <id> --log-failed` prints nothing, and the jobs API returns
  `"steps": []` for that job.
- The job's check-run annotations say why. Read them with the job id:

```
gh api repos/{owner}/{repo}/check-runs/<job-id>/annotations --jq '.[].message'
```

The message is `The job was not acquired by Runner of type hosted even after multiple attempts`. It sits
beside repeated notices that macOS arm64 runners have long queues because of limited capacity.

Seen on 2026-11-25 on `macos-latest`. The same commit's Windows job in that run succeeded, and a release
workflow that started 30 minutes later got a macOS runner and built normally.

## What to do

Nothing in the repo needs fixing. Re-run only the failed job:

```
gh run rerun <run-id> --failed
```

It runs on the same commit, and its result replaces the cancelled one on the branch's status.
