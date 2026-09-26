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

Do not count CRs with plain `grep -c` in Git Bash. Its GNU grep 3.0 reads files in text mode and strips the CR, so a CR-at-end-of-line pattern reports 0 on a CRLF file; `grep -U` counts it correctly (measured 2026-09-25). A count claiming *every* line of a file is CRLF is the opposite symptom: the CR never reached grep and the pattern collapsed to `$`, which matches every line. For a definitive answer read `w/` above, or count the bytes (`b"\r\n" in data`).

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

**`git update-index --refresh` does NOT fix this** — it re-stats but sees the size mismatch and still reports "needs update."

**Clear it with `git add <path>`, and reach for `git checkout` only per-path.** Staging re-hashes the file through its filters and rewrites the index entry; when the content is identical it stages nothing, so `git status` goes clean and `git diff --cached` stays empty. `git checkout -- .` also works — it rewrites the working tree from the index, producing LF files under `autocrlf=input` — but it overwrites *every* path, discarding all real uncommitted changes in the repo. That matters because the workflow most likely to meet a phantom is `/commit`, which runs on a dirty tree by premise: the phantom appears in the same status listing as the work about to be committed, so the bare `.` form would destroy exactly what the session was there to save.

**Prove the content is identical before either fix.** On a genuinely modified file `git add` quietly stages the change instead of revealing a phantom, so the check comes first:

```bash
git show :<path> | cmp - <path>   # exit 0 → working bytes match the stored blob
git ls-files -v <path>            # leading H → not assume-unchanged / skip-worktree
```

Compare hashes instead only with `git hash-object --path=<path> <file>`; the bare `git hash-object <file>` skips the path's clean filter and agrees with the index by luck on an already-LF file.

The signature is `git status` naming the path while every diff form is empty — `git diff`, `git diff --stat` and `git diff --raw` all print nothing. A wrapper that reports an uncommitted change from `status` next to an empty diff is showing this, not a broken probe.

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

Prefer writing `text=auto eol=lf` on the rule over deleting `-text` and inheriting the global. The third row of the table above is a *borrowed* protection: it holds only while that machine has `* text=auto eol=lf` in its `core.attributesFile`, which is per-machine, uncommitted, and absent on CI. An explicit per-path attribute travels with the repo.

**To tell borrowed from owned, suppress the global and ask again.** `git check-attr` merges every source, so on the machine doing the borrowing it answers `auto`/`lf` and proves nothing about the repo:

```bash
git check-attr text eol -- <path>                                    # auto / lf   (looks fine)
git -c core.attributesfile=/dev/null check-attr text eol -- <path>   # unspecified / unspecified
```

A second answer of `unspecified` means the repo supplies nothing and every clone is on its own. Where `core.autocrlf` and `core.eol` are both unset — the common macOS case — this isolates the cause completely: exactly one thing was doing the work, and removing it shows what a fresh clone elsewhere sees.

**Probe committed content, not your own working tree.** The moment the fix is in the tree the second line answers `auto`/`lf` from the uncommitted edit, so the probe silently stops measuring the repo and starts measuring you — the same substitution the whole trap is made of, one layer up. Check the committed state out in a throwaway worktree and probe that:

```bash
git worktree add --detach /tmp/probe origin/main
git -C /tmp/probe -c core.attributesfile=/dev/null check-attr text eol -- <path>
git worktree remove --force /tmp/probe
```

Run it on both states and the pair reads as a before/after: `unspecified` at `origin/main` proves the bug is really in the repo rather than in one machine's config, and `auto`/`lf` in the edited tree with the global still suppressed proves the new rule stands on its own.

Two things make this easy to skip. It **hides behind a comment that looks like the problem was handled**: measured across five repos on 2026-09-02, four carried a crypt rule with no `text`/`eol`, and two sat directly beneath a comment explaining the CRLF churn and correctly rejecting `-text` for the right reason — so a reviewer greps for the trap, finds it apparently considered, and moves on. And on an already-LF repo the fix is a **no-op in the working tree** — the path does not even appear in `git status`, because the global had already normalized the blob. That silence is the correct outcome, not evidence the change did nothing.

**Audit on the attribute present in the rule, never on whether the surrounding prose discusses the problem.** Declining `-text` and specifying `text=auto eol=lf` look like one decision and are two. The repo with the most thorough comment was the last one fixed, precisely because it looked handled.

**`text=auto` has an escape hatch, and it makes the fix look like it worked when it did not.** Git converts a file only "if it is text **and the file was not already in Git with CRLF endings**" — so on a path whose stored blob is already CRLF, adding `text=auto` changes nothing at all, silently. Clear it with `git add --renormalize <path>`. An unconditional `text` has no such precondition, but it also forfeits the binary heuristic, so `text=auto` plus a renormalize is the better pair for a glob that might match a binary secret later.

Where the CRs come from on Windows: the mingw64-native openssl that Git Bash puts on PATH writes stdout in text mode, so `openssl enc -a` emits CRLF-terminated base64; the msys `/usr/bin/openssl` emits LF. Repointing `transcrypt.openssl-path` at the latter is a real fix but a per-machine one — it does nothing for anyone else's clone, which is why the attribute is the right layer.

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

## Python scripts that edit files write CRLF

Write edited text back with `Path.write_bytes(text.encode("utf-8"))` or `open(path, "w", newline="\n")`, never plain `write_text` — on Windows, text mode translates every `\n` to `\r\n`. A read-replace-write edit script therefore turns an LF file into an all-CRLF one while changing nothing visible, and nothing warns until `git diff` does. One change set on 2026-09-25 converted 14 files this way; under `core.autocrlf=input` the commit is still LF, but every diff floods with the CRLF warning and the working copies stay converted.

To find and undo it, count per file and rewrite as bytes:

```python
b = p.read_bytes()
if b.count(b"\r\n"):
    p.write_bytes(b.replace(b"\r\n", b"\n"))
```

## Key Insight

The `eol=lf` setting only affects what git writes on checkout — it does not retroactively fix existing working copies. Files created or edited by Windows tools between checkouts will have CRLF until the next `git checkout` or manual conversion.
