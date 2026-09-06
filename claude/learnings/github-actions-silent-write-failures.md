# A CI job that reports success while writing nothing

Measured on 2026-09-03, reconstructing why a Homebrew cask had been an empty file for two releases
without a single alert. The write broke, and then three independent mechanisms each failed to say so.
None of them is exotic; the combination is the default configuration of a very ordinary bump job.

The shape is worth knowing on its own, because every layer that should have caught it was present and
green. The bug is not that nothing checked. It is that everything that checked was checking liveness.

## The write: a failed command substitution inside an argument does not trip `set -e`

```yaml
runs-on: macos-latest          # moved here to run `brew audit`
...
    gh api --method PUT "repos/$OWNER/$REPO/contents/$CASK" \
      -f message="chore: bump to $VERSION" \
      -f content="$(base64 -w0 "$CASK")" \
      -f sha="$SHA"
```

GNU coreutils `base64` takes `-w0` to disable line wrapping. **BSD `base64`, which is what
`macos-latest` has, has no `-w` at all** and exits non-zero:

```
base64: invalid argument Casks/example.rb
Usage:	base64 [-Ddh] [-b num] [-i in_file] [-o out_file]
```

Under `set -euo pipefail` that is *not* fatal, because the failure happens inside a command
substitution used as a **word in an argument list**. `set -e` only reacts to the exit status of the
enclosing simple command, and the enclosing command is `gh api`, which ran fine. The substitution
expands to the empty string, so the API receives `content=""` and does exactly what it was told:
commits an empty file. HTTP 200. Step exits 0. Job green.

Portable forms, both of which work on GNU and BSD:

```bash
base64 -i "$CASK" | tr -d '\n'
openssl base64 -A -in "$CASK"
```

The general rule: `$( )` failures are invisible to `set -e` in argument position. When a substitution
produces something that must not be empty, bind it to a variable first and assert on it.

```bash
CONTENT=$(base64 -i "$CASK" | tr -d '\n') || exit 1
[ -n "$CONTENT" ] || { echo "::error::empty base64 for $CASK"; exit 1; }
```

## Silence 1: a green job sends no notification

GitHub's Actions email/web notifications fire on **failure**. A job that writes garbage and exits 0 is
indistinguishable, to the notification system, from a job that did its work. Four consecutive
`repository_dispatch` runs concluded `success` while committing an empty file, and the repository
owner heard nothing about any of them.

## Silence 2: the validation step was gated by a condition the bug made false

```yaml
- name: Rewrite the cask
  run: |
    if git diff --quiet -- "$CASK"; then
      echo "cask already at $VERSION, nothing to do"
      echo "CHANGED=false" >> "$GITHUB_ENV"
    else
      echo "CHANGED=true" >> "$GITHUB_ENV"
    fi

- name: Validate the rewritten cask
  if: env.CHANGED == 'true'      # <- skipped in exactly the case that needed it
```

`CHANGED` is derived from `git diff --quiet` alone and never reads the artifact's actual version, so
"the file is already empty and my rewrite produced nothing" and "the file is already correct" are the
same observation. The run log reads `cask already at 1.11.0, nothing to do` about a **0-byte file**.
A step that is skipped renders in the UI as a pale check, not a warning, so *not run* looked like
*passed*. Compare `feedback_not_run_is_not_pass`.

The fix is to assert the postcondition instead of inferring it from a diff:

```bash
# after the PUT, re-read what is actually committed
BODY=$(gh api "repos/$OWNER/$REPO/contents/$CASK" --jq '.content' | base64 -d)
[ -n "$BODY" ] || { echo "::error::committed file is empty"; exit 1; }
grep -q "version \"$VERSION\"" <<<"$BODY" || { echo "::error::version not $VERSION"; exit 1; }
```

## Silence 3: `GITHUB_TOKEN` writes cannot trigger the repo's own test workflow

This is documented GitHub behaviour and it is a loop-prevention feature, not a bug: **an event raised
by a commit pushed with the automatic `GITHUB_TOKEN` does not start another workflow run.** So the
repository's own `Tests` workflow, which lints and audits the artifact on `push`, has never once run
on a bot bump. Every `Tests` run in that repo's history is on a human push.

Consequence: the job that writes an artifact is structurally the *only* thing that can validate it,
because nothing downstream will be triggered by its commit. Any CI design that says "the write job
stays simple, the test job will catch problems" is broken by default when the writer uses
`GITHUB_TOKEN`. Either validate inside the writing job (preferred, and it can assert the
postcondition), or push with a PAT / GitHub App token, which does raise events.

## How to check whether this is happening to you right now

Green runs prove nothing here, so go and look at the artifact:

```bash
gh api repos/OWNER/REPO/contents/PATH --jq '{size, sha}'
```

`"size": 0` with `"sha": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"` is git's canonical **empty blob**
hash. Seeing that hash anywhere is conclusive: something committed an empty file. Then walk the file's
history to find which commit did it, and read that run's log:

```bash
gh api "repos/OWNER/REPO/commits?path=PATH" --jq '.[] | [.sha[0:7], .commit.author.date, .commit.message] | @tsv'
```

## The transferable rule

Assert **identity**, not liveness. An exit code says a process ran; a 200 says a request was accepted.
Neither says the right bytes are in the right place. Any automation whose whole purpose is to produce
an artifact should finish by reading that artifact back and asserting something that could only be
true if the work succeeded: a version string, a non-zero size, a checksum. Everything else is a check
on the plumbing.

Related: `verify-the-detector-before-the-negative.md` (a search that could not have found the thing),
`homebrew-cask-unsigned-macos-app.md` (which recommends the Contents-API bump pattern this page's
first section shows how to get wrong), `bash-portability.md`.
