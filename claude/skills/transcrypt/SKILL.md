---
name: transcrypt
description: >-
  Encrypt files in a git repo with transcrypt using the shared Doppler-stored passphrase, or unlock
  (decrypt) an already-encrypted repo after a fresh clone. Designated files stay plaintext in the working
  tree but are stored encrypted in git history.
  TRIGGER when: the user wants to commit a file encrypted, protect a sensitive committed doc, set up
  transcrypt in a repo, or decrypt/unlock secret files after cloning.
  DO NOT TRIGGER when: the secret is an env-style credential (API key, token, password) that belongs in
  Doppler/`.env`, not a committed file.
allowed-tools: Bash(command -v transcrypt:*), Bash(transcrypt:*), Bash(curl:*), Bash(chmod:*), Bash(hash:*), Bash(git:*), Bash(doppler secrets get:*), Bash(mv:*), Bash(test:*), Bash(grep:*), Bash(printf:*), Bash(head:*), Read, Write, Edit
---

# Transcrypt (shared-key file encryption)

Transcrypt stores designated files **encrypted in git** but keeps them **plaintext in the working tree**
via git clean/smudge filters. One shared passphrase lives in Doppler (`tools/prd` → `TRANSCRYPT_KEY`), so
the same key works across every repo and machine. Files are marked by the `*.secret.*` naming convention
in `.gitattributes` (e.g. `notes.secret.md`, `config.secret.json`).

## Context
- transcrypt installed: !`command -v transcrypt >/dev/null 2>&1 && echo INSTALLED || echo MISSING`
- this repo's transcrypt config: !`git config --get-regexp '^transcrypt\.' 2>/dev/null || echo NOT-CONFIGURED`
- encrypt attribute in .gitattributes: !`test -f .gitattributes && grep -i crypt .gitattributes || echo NONE`
- working tree: !`git status --short 2>/dev/null || echo "(not a git repo)"`

## The shared key — never generate a new one

Every init/unlock uses the Doppler-stored passphrase and `aes-256-cbc` (the standard cipher for these
repos). This one sequence is referenced throughout; the key is never printed. Run it from the repo root,
and keep all three lines — the bracket around the middle one is explained below:

```
git config core.hooksPath "$(git rev-parse --path-format=absolute --git-common-dir)/hooks"
transcrypt -c aes-256-cbc -p "$(doppler secrets get TRANSCRYPT_KEY --project tools --config prd --plain)" -y
git config --unset core.hooksPath
```

Doppler's auth is **directory-scoped**, so read the key from a scoped directory. Fetching it from an
unscoped path (a temp dir, say) fails with "you must provide a token" and transcrypt then dies on an
empty password — capture the key into a variable before changing directories if the init runs elsewhere.

Init also refuses on a **dirty tree** — if a tracked file is modified, stash just it first
(`git stash push <file>`), init, then `git stash pop`. Untracked files don't block it.

**Why the `core.hooksPath` bracket.** Transcrypt writes its `pre-commit-crypt` helper into whatever
`core.hooksPath` resolves to, then copies it to `pre-commit` when that name is free — hardcoded in
`save_helper_hooks`, with no flag to skip it. A **global** hooksPath makes "whatever it resolves to" the
shared dir, so one repo's helper clutters the hooks directory every repo uses, and transcrypt prints a
"Cannot install Git pre-commit hook script because file already exists" warning because the guarded
global `pre-commit` is already sitting there. Pointing it at the repo's own git dir for the duration puts
the helper in `.git/hooks/` — exactly where transcrypt would have put it on a machine with no global
hooksPath — per-repo, untracked, and inert once the override is removed. Nothing is lost: the global hook
already runs the same check (see "Pre-commit safety net" below). The bracket is a no-op on a machine
with no global hooksPath, so it is unconditional.

(Verified 2026-08-17 against transcrypt 2.3.2 and git 2.39: with the bracket the global hooks dir is
untouched, no warning is printed, and encryption still works once the override is removed. Deleting the
leftover afterwards — what this skill advised until now — is not available to Claude: the auto-mode
classifier reads a write to the global hooks dir as audit tampering and denies it. Prevention is the only
path, and a repo initialized before this fix needs the user to remove the stale `pre-commit-crypt`
themselves.)

## Step 0 — ensure transcrypt is installed

If **transcrypt installed** (Context) is `MISSING`, install it:

```
curl -fsSL https://raw.githubusercontent.com/elasticdog/transcrypt/main/transcrypt -o ~/bin/transcrypt && chmod +x ~/bin/transcrypt && hash -r
```

If `~/bin` isn't on PATH, pick another PATH directory. **Classifier caveat:** the auto-mode classifier may
block *executing* transcrypt the first time (it's a fetched script). If blocked, ask the user to approve the
permission prompt or add a `Bash(transcrypt:*)` rule to their settings — do **not** work around the denial.

## Pick the mode

From Context and the user's request:

- **Encrypt a file** — the user named a file/doc to protect → do **A**.
- **Unlock after clone** — **encrypt attribute** shows `crypt` but **this repo's transcrypt config** is
  `NOT-CONFIGURED` (secret files read as ciphertext locally) → do **B**.
- **Setup only** — the user wants transcrypt ready with no file yet → run A step 1, then stop.

## A — Encrypt a file

1. If **this repo's transcrypt config** is `NOT-CONFIGURED`, initialize with the shared-key sequence above.
2. Ensure `.gitattributes` carries the encrypt pattern; add this line if missing (**encrypt attribute** is
   `NONE`):
   ```
   *.secret.* filter=crypt diff=crypt merge=crypt
   ```
   Do **not** add `-text` here. Transcrypt stores base64, which is text — marking it binary disables git's
   line-ending normalization, so a Windows clone commits CRLF-wrapped ciphertext and a macOS/Linux clone
   rewrites it to LF, churning the file on every cross-platform round trip. Leaving it normalizable is what
   keeps the blob byte-identical across platforms (see `~/.claude/learnings/git-line-endings.md`).
3. Ensure the target matches the pattern. If it isn't already `*.secret.*`, rename it —
   `mv <dir>/<name>.<ext> <dir>/<name>.secret.<ext>` — and update any references to the old name (grep the
   repo).
4. Stage so the clean filter encrypts it: `git add .gitattributes <the .secret file>`.
5. **Verify** — the index blob must be ciphertext while the working tree stays plaintext:
   - `git show :<the .secret file> | head -3` → openssl/transcrypt ciphertext, **not** the plaintext.
   - `head -1 <the .secret file>` → still the readable first line.
   If the index shows plaintext, **STOP** — the filter didn't run (transcrypt not initialized, or the
   `.gitattributes` pattern doesn't match). Fix before anything is committed.
6. Do **not** commit. Report that the file is staged, encrypted, and ready; the commit happens via `/commit`
   with the rest of the change set.

## B — Unlock a repo after clone

Secret files read as ciphertext because transcrypt isn't configured on this machine yet. Run the shared-key
sequence above; transcrypt decrypts every `*.secret.*` file in place. Confirm with
`head -1 <a .secret file>` (readable plaintext).

## Out of scope

- Do **not** commit or push — staging + verify only; `/commit` owns the commit.
- Do **not** generate a new passphrase — always the Doppler `TRANSCRYPT_KEY`.
- Do **not** put env-style secrets (keys, tokens, passwords) in committed files — those belong in Doppler.
- Do **not** work around a classifier denial on executing transcrypt — ask the user to approve or allowlist.

## Pre-commit safety net (already global)

A guarded transcrypt pre-commit hook is installed globally (`~/.git-hooks/pre-commit` via
`core.hooksPath`, tracked in the dotfiles repo). It blocks committing a `*.secret.*` file that lacks the
encrypted "Salted" magic, and no-ops in non-transcrypt repos. So **ignore transcrypt's "manually install
the pre-commit script" message** if you ever see it — the global hook already covers every repo; no
per-repo hook install is needed. The `core.hooksPath` bracket in the shared-key section keeps transcrypt's
own copy inside `.git/hooks/`, so that message should not appear at all.

## Fresh-machine note

On any new clone, `*.secret.*` files stay ciphertext until mode **B** runs once. The `.gitattributes` and the
encrypted blobs are committed; the key is not — it lives only in Doppler.
