# Claude Code allow rules: what they match, and how a local file rots

A project's `.claude/settings.local.json` is gitignored and per-machine, and every "always allow" click appends to its `permissions.allow` list. Nothing reviews it, so it collects rules that match nothing and rules that pre-approve far more than the one command that was clicked.

## A `Write(path)` allow rule never matches

Claude Code checks every file-editing tool, Write included, against `Edit(path)` rules only, and warns about a `Write(path)` allow rule when a session starts or exits:

```
Permission allow rule (.claude\settings.local.json): Write(D:/<repo>/config/deploy.env) is not matched by file permission checks — only Edit(path) rules are.
```

Observed 2026-09-25 on a pair of rules, one with forward slashes and one with backslashes, that no tool call in the project's transcripts had written. The warning proposes `Edit(D:/…)`, but absolute paths in these rules are otherwise root-anchored with `//` (`Read(//c/Users/<user>/**)`), and the unanchored drive-letter form was not tested. Deleting the rule is the safe fix for a file written rarely.

A hook's `if` field is a different matcher: `"if": "Write(//**/SKILL.md)"` does gate a hook on writes (see `claude-code-integration.md`).

## What accumulates

An audit of 16 projects' local files on 2026-09-25 found about 700 rules. A second agent verified 156 as risky, 31 as stale, 47 as duplicates and about 180 as one-off commands that will never recur. The risky ones fell into a few shapes:

- **Blanket prefixes:** `Bash(git:*)`, `bash:*`, `python:*`, `node:*`, `rm:*`, `curl:*`, `gh api:*`, each approving every destructive or outward-facing form of the tool.
- **A prefix cut at a space:** `Bash("/c/Program Files/GitHub:*)` matches every `gh` command invoked by its full path, `gh repo delete` included.
- **Fragments of one approved loop** saved as separate rules: `do:*`, `for f:*`, `done`. The `do` fragment approves the body of any loop on its own.
- **One-off history rewrites saved for good:** an interactive `git rebase -i <sha>` with scripted editors, re-runnable unprompted.
- **`npx` of a package that does not exist on npm:** npx fetches and runs whatever is later published under that name.
- **`Skill(<name>)` for a skill since renamed:** it matches nothing.

## Pruning

Under auto mode, a command with no allow rule goes to the classifier rather than to a prompt, so removing a rule costs little.

When a narrow rule was filed as a duplicate of a broad risky one (`git log:*` under `git:*`), removing both loses harmless access along with the risk. Once the broad rule goes, the narrow one is the only cover left; keep it unless it is risky in its own right, as `git reset:*` under `git:*` is.
