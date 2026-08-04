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

## `-text` Disables eol Conversion Entirely

Marking a path `-text` does not merely leave `text` unspecified — it declares the file **binary**, and git then skips end-of-line conversion for it completely. An `eol=lf` inherited from a global gitattributes still *appears* in `git check-attr` but is dead:

```
$ git check-attr text eol -- notes.secret.md
notes.secret.md: text: unset     <- binary, so the eol below never applies
notes.secret.md: eol: lf
```

Internally `crlf_action = CRLF_BINARY` short-circuits before `eol` is consulted. A global `* text=auto eol=lf` therefore protects nothing on a path that a repo-local rule opted out with `-text`.

Symptom: one file churns CRLF↔LF across machines while every other file in the same repo stays LF.

## Filters Run Before eol Normalization (check-in)

On `git add`, git applies the **clean filter first**, then normalizes the filter's *output*. So a filter that emits platform-dependent line endings still produces a canonical blob — provided the path is treated as text:

| local attribute | effective | resulting blob |
|---|---|---|
| `-text` | `unset eol=lf` | keeps whatever the filter emitted |
| `text eol=lf` | `set eol=lf` | normalized to LF |
| *(none, inherits global `text=auto eol=lf`)* | `auto eol=lf` | normalized to LF |

On checkout the order reverses: eol conversion happens *before* the smudge filter.

This matters for base64-armored filters (transcrypt, git-crypt in ASCII mode). Their stored form is text, so leaving it normalizable is exactly what keeps blobs byte-identical across platforms — marking it `-text` is what makes them diverge. Only genuinely binary filter output needs `-text`.

## Diagnosing a Filtered Blob That Churns

To tell "content actually changed" from "only the encoding changed", compare size and CR count rather than the diff (git shows filtered files as `Bin`):

```bash
git cat-file blob <sha> | wc -c
git cat-file blob <sha> | grep -c $'\r'
```

A byte delta exactly equal to the line count is CRLF vs LF, not a content change. For transcrypt specifically, the 8-byte salt after the `Salted__` magic is derived by HMAC over the plaintext, so two blobs sharing a salt hold identical plaintext:

```bash
git cat-file blob <sha> | openssl base64 -d | head -c 16 | xxd -p
```

## Key Insight

The `eol=lf` setting only affects what git writes on checkout — it does not retroactively fix existing working copies. Files created or edited by Windows tools between checkouts will have CRLF until the next `git checkout` or manual conversion.
