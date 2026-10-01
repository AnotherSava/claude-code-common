# Reading the owning account out of a git remote URL

Deciding whose repo a clone is, or whether it is a fork, comes down to reading an account name out
of `remote.<name>.url`. A regex that takes "the segment before the repo name" looks right on the
common URLs and is wrong on two classes nobody tests: local paths, which it reads as owned by
their parent folder, and SSH host aliases, which a stricter regex then drops entirely.

## What git accepts

| Form | Example | Owner |
|---|---|---|
| scp-like | `git@github.com:owner/repo.git` | `owner` |
| scp-like, no user | `github.com:owner/repo` | `owner` |
| scp-like, SSH alias host | `git@gh-work:owner/repo.git` | `owner` — the host has no dot |
| URL with scheme | `https://github.com/owner/repo.git`, `ssh://git@host:22/owner/repo` | `owner` |
| nested groups | `git@gitlab.com:group/sub/repo.git` | `group` — the first segment |
| local path | `C:/work/other`, `/home/me/src/proj`, `../sibling` | none |
| `file://` URL | `file:///C:/work/x`, `file://server/share/repo` | none — even with a host part |

Git treats `host:path` as scp-like SSH only when the colon comes before any slash, and on Windows
a single letter before the colon is a drive, not a host. So requiring a dot in the host to keep
`C:/work` out also rejects every `~/.ssh/config` alias, which is how one machine commonly
runs several GitHub accounts. Require a host of two characters or more instead, matching git's own
drive check. `file://host/...` is a UNC or local path and names no account. A URL with nothing
after the owner (`https://github.com/owner`) is not a repo remote.

A pattern that covers the table, with the owner in group 1:

```python
REMOTE_URL_RE = re.compile(r"^(?:(?!file:)[a-z][a-z0-9+.-]*://(?:[^@/]+@)?[^/]+/|(?:[^@/:]+@)?[^@/:\\]{2,}:)"
                           r"([^/]+)/[^/].*?(?:\.git)?/?$", re.IGNORECASE)
```

Read the config with section names compared case-insensitively and spaces removed
(`[remote "origin"]`). A linked worktree's `.git` is a file pointing at
`<main>/.git/worktrees/<name>`, which has no `config` of its own, so the remote is two levels up.

## Remotes do not travel with the repo

`.git/config` is never committed, so every remote is a fact about one clone. A fresh `git clone` of
a fork has `origin` and no `upstream` until someone adds it. Anything committed must therefore not
be validated at read time against a remote: a record that a fork made a choice reads as invalid in
the fork's own clone on another machine. Check the remote when the choice is written, and let the
committed result travel with the repo after that.
