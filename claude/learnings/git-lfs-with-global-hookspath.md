# Git LFS objects are not uploaded when core.hooksPath is set

Make the global `pre-push` hook call `git lfs pre-push "$@"` itself, as this repo's `git/hooks/pre-push` does. Git LFS installs its hooks wherever `core.hooksPath` points. With a global setting that is the global hooks directory: `git lfs install`, `git lfs track` and the first `git add` of an LFS file all find its existing non-LFS `pre-push` and stop. `track` and `add` stop silently; `install` and `update` fail with `Hook already exists: pre-push`. So no LFS hook is installed anywhere, `post-checkout`, `post-commit` and `post-merge` included (those three only matter for lockable files). Without the call, `git push` succeeds and sends a commit whose LFS pointer names an object the server does not have. Nothing fails: the only sign is that the push output has no `Uploading LFS objects` line.

Measured 2026-09-28 (git 2.39.1, git-lfs 3.3.0): pushing a commit with one new `.3mf` pointer under a global `core.hooksPath` whose `pre-push` only checked authorship and signatures printed only the ref update.

**Never run `git lfs update --force` or `git lfs install --force`, the remedy that error message offers.** With a global `core.hooksPath` it replaces the global `pre-push` with the stock three-line LFS stub, so every repo loses the checks that hook carries. On this setup `~/.git-hooks` links to this repo's `git/hooks/`, so the command overwrites a tracked file.

## Chaining LFS from a global hook

These details decide whether the call works and what it costs:

- **Buffer stdin first.** Git writes the ref lines to the hook's stdin once, and `git lfs pre-push` needs the same lines, so a hook that reads them in its own loop has to capture them (`input=$(cat)`) and pipe them on.
- **Run it only where the push can carry LFS content:** a local object store exists at `$(git rev-parse --git-common-dir)/lfs/objects`, `lfs.storage` is set, or a pushed commit's root `.gitattributes` names `filter=lfs`. Ungated, the call adds about 4 seconds to every push in a repo with no LFS at all: two SSH attempts at `git-lfs-transfer`, an `ls-remote`, `git-lfs-authenticate`, and a POST to the server's `locks/verify` (measured 2026-09-28 against GitHub). Each condition alone misses a real case. `lfs.storage` moves the store out of the git dir. A bare `git clone --mirror` holds pointers with no store at all; there `git lfs pre-push` refuses the push because the objects are missing, which is the answer a host migration needs before the old host is retired.
- **Test for `lfs/objects`, not `lfs/`.** The call itself creates `lfs/cache` and `lfs/tmp` in a repo that stores nothing. `lfs/objects` appears once the LFS filter has run on a matching path, though not always with an object in it: a `GIT_LFS_SKIP_SMUDGE=1` clone creates the directories empty.
- **Fail the push when LFS content is possible and `git-lfs` is not on `PATH`.** Skipping the call there sends pointers without objects, which is the failure the call exists to prevent.

## Repairing a push that skipped the upload

Push every object the branch references:

```bash
git lfs push --all origin <branch>
```

`--all` is what makes it work after the ref has been pushed. Without it, `git lfs push origin <branch>` printed nothing and exited 0, because it skips objects reachable from remote refs it believes are already pushed. For known objects, `git lfs push --object-id origin <oid>...` takes several oids at once. List them with `git lfs ls-files --long --all`: without `--all` it shows only the versions in `HEAD`, so a file the pushed range changed twice leaves its older object unlisted.

## Checking that the server has the object

Ask the LFS batch API. It needs no auth on a public repo, and it is the only check here that answered correctly:

```bash
curl -s -X POST -H "Accept: application/vnd.git-lfs+json" -H "Content-Type: application/vnd.git-lfs+json" \
  -d '{"operation":"download","transfers":["basic"],"objects":[{"oid":"<oid>","size":<size>}]}' \
  https://github.com/<owner>/<repo>.git/info/lfs/objects/batch
```

An object the server has comes back with `actions.download`. Fetch that `href` and compare its `sha256sum` with the oid for proof. Do not use `media.githubusercontent.com/media/<owner>/<repo>/<ref>/<path>` for this: it returned 404 both before and after the upload in the same session.

## Testing against a local bare remote

A bare repo on disk is a full LFS remote: git-lfs uploads to a `file://` URL through its built-in `lfs-standalone-file` adapter, into `<remote.git>/lfs/objects/<oid[0:2]>/<oid[2:4]>/<oid>`, where the test can look for the file. On Windows, write the URL with a drive letter (`file:///D:/…`, from `cygpath -m`). Native git-lfs cannot resolve a Git Bash `/d/…` path: the adapter fails with `chdir /d/…: The system cannot find the path specified`, and the push reports only `EOF`.

Give each scratch repo its own `core.hooksPath` before any `git lfs` command runs in it, or git-lfs aims at the global hooks directory as described above.
