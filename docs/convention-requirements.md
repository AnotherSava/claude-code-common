# What the conventions require

The set as it stands at v10. Each row is one **version** — a change a repo takes on by running `/adopt` once. A ✓ means the version also handed a **rule** to the checker, so the property keeps being asserted at every commit rather than only on the day it was adopted.

[Conventions](convention-versions.md) explains how versions, rules and the record work. This page is only what they ask for.

| | Requires | Applies when | Re-checked |
|---|---|---|---|
| **v1** | the memo backlog is a directory of one file per memo, addressed ones in `done/` carrying the date they were closed | the repo has a backlog | |
| **v2** | a project `.gitignore` hides nothing the repo must commit, and repeats no rule that belongs to the machine's global excludes file | the repo commits a `.gitignore`, or git hides a required path | ✓ |
| **v3** | each memory file opens with frontmatter, and `MEMORY.md` links them by bare name | `.claude/memory/` holds a memory file | ✓ |
| **v4** | a transcrypt-encrypted path normalizes its line endings, so the same file does not re-encrypt differently on each machine | `.gitattributes` marks something `filter=crypt` | ✓ |
| **v5** | a Node project declares its `engines.node` range, enforces it rather than leaving it advisory, and pins the npm version | the repo holds a `package.json` a person maintains | ✓ |
| **v6** | a LICENSE sits at the root, because a repo carrying none grants nothing to anyone who obtains a copy | always | |
| **v7** | a Jekyll `remote_theme` names a tag, so the published site cannot change because someone else pushed to their default branch | the repo has a `docs/_config.yml` | ✓ |
| **v8** | a compose service is named after its project, because the service key becomes a DNS alias on every network it joins and a generic one collides with a neighbour's | the repo deploys to the shared host | ✓ |
| **v9** | the commit gate runs whatever actually gates the deploy, and calls the conventions checker | always | |
| **v10** | every memo v1's split produced sits on the side its checklist marker asked for, since v1 asserted only that each line reached *some* file | the repo's backlog was once a `memos.md` checklist | |

Each version is gated on one prerequisite, and versions that shared one were merged rather than kept apart: v1 covers every transformation a backlog needs, v2 both halves of what a `.gitignore` may hold, v5 the three Node properties in the order they depend on each other, v9 both halves of the gate.

## Rules that need no adoption

Two rules are gated by no version and run in every repo from the moment its gate calls the checker, whatever its number. Both assert something about *this machine's* relationship to the repo, which no version could ever settle — the same repo arrives on a second machine with the work genuinely not done.

| | Requires |
|---|---|
| **`memory-cache-linked`** | this machine's memory cache for the repo points into the repo's committed `.claude/memory/` |
| **`install-links-present`** | every symlink and git setting the install blocks create is in place on this machine |

## Reading the live set

The table above is written by hand and can fall behind the folders. What the machine actually holds:

```
python ~/.claude/conventions/engine.py versions
```
