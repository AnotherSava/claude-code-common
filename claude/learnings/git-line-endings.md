# Git Line Endings on Windows

How CRLF/LF issues arise on Windows and how to resolve them. Applicable to any repo where contributors use Windows alongside Linux/macOS.

## The Problem

Windows editors save files with CRLF (`\r\n`) line endings by default. Git repos conventionally store LF (`\n`). When a Windows working copy has CRLF but the index expects LF, git emits:

```
warning: in the working copy of 'file', CRLF will be replaced by LF the next time Git touches it
```

This warning appears on every `git diff` or `git add` until the working copies are normalized.

## Git Config Settings

Two global settings control line-ending behavior:

- **`core.autocrlf`** — controls conversion on add/checkout:
  - `input` — convert CRLF → LF on `git add`, but don't convert on checkout (recommended for Windows when you want LF everywhere)
  - `true` — convert CRLF → LF on add, LF → CRLF on checkout (Windows default in some installers)
  - `false` — no conversion at all

- **`core.eol`** — sets the line ending for the working copy when `text=auto` is active:
  - `lf` — working copies use LF
  - `crlf` — working copies use CRLF
  - `native` — use the OS default

The recommended Windows config for LF-everywhere repos:
```
git config --global core.autocrlf input
git config --global core.eol lf
```

## Diagnosing

Check which tracked files have CRLF in the working copy:
```bash
git ls-files --eol | grep "w/crlf"
```

Output columns: `i/<index-eol>  w/<working-eol>  attr/<attributes>  <filename>`

## Fixing Existing Working Copies

Even with correct git config, existing working copies keep their CRLF until explicitly converted. Converting all tracked files in-place:

```bash
git ls-files --eol | grep "w/crlf" | sed 's/.*\t//' | while IFS= read -r f; do
  sed -i 's/\r$//' "$f"
done
```

The `sed 's/.*\t//'` extracts the filename (last tab-separated field). The inner `sed` strips carriage returns.

After conversion, `git diff` shows no changes for files that were already LF in the index — the normalization is invisible to git because the index content didn't change.

## Enforcement with .gitattributes

A `* text=auto eol=lf` rule ensures consistent behavior regardless of individual git config. This can live in two places:

- **Global gitattributes** (`core.attributesFile`, e.g. `~/.gitattributes`) — applies to all repos on the machine. Good for personal setups where you always want LF.
- **Per-repo `.gitattributes`** at the repo root — committed to the repo, so it enforces the policy for all contributors regardless of their local config. Preferred for shared/open-source repos.

```
* text=auto eol=lf
```

To renormalize after adding a `.gitattributes`:
```bash
git add --renormalize .
git commit -m "chore: normalize line endings"
```

## Phantom "Modified" Files (No Actual Diff)

`git status` can show files as modified even when `git diff HEAD` produces no output. This happens when files on disk differ from what the index stat cache expects (different size/timestamp), but after content normalization (e.g. via `core.autocrlf`) the content is identical.

Common cause: a tool or editor converted CRLF→LF on disk, so the file size changed (fewer bytes), but `autocrlf=input` normalizes to LF when comparing, making the content match HEAD.

**`git update-index --refresh` does NOT fix this** — it re-stats but sees the size mismatch and still reports "needs update." The fix is:

```bash
git checkout -- .
```

This re-writes the working tree from the index, and with `autocrlf=input` the checkout produces LF files. Now disk matches the index stat cache and status is clean.

## Key Insight

The `eol=lf` setting only affects what git writes on checkout — it does not retroactively fix existing working copies. Files created or edited by Windows tools between checkouts will have CRLF until the next `git checkout` or manual conversion.
