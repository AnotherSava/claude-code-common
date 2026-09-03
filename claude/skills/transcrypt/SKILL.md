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
- openssl shim wired: !`git config --get transcrypt.openssl-path 2>/dev/null || echo "none — expect the 'deprecated key derivation' warning on git commands; see that section"`

## The shared key — never generate a new one

Every init/unlock uses the Doppler-stored passphrase and `aes-256-cbc` (the standard cipher for these
repos). This one sequence is referenced throughout; the key is never printed. Run it from the repo root,
and keep all four lines — the bracket around the middle one is explained below:

```
git config core.hooksPath "$(git rev-parse --path-format=absolute --git-common-dir)/hooks"
transcrypt -c aes-256-cbc -p "$(doppler secrets get TRANSCRYPT_KEY --project tools --config prd --plain)" -y
git config --unset core.hooksPath
git config --local transcrypt.openssl-path "$(sh ~/.claude/skills/transcrypt/scripts/ensure-openssl-shim.sh)"
```

The fourth line silences OpenSSL's `deprecated key derivation` warning, which every crypt filter otherwise
prints on `git status`, `git add` and `git diff` for the life of the repo. It is part of the sequence rather
than an optional extra because the warning is pure noise that has already crowded out the result of a real
check, and because **`transcrypt init` rewrites `transcrypt.openssl-path`** — so anything that re-inits has
to re-apply it anyway. The helper is idempotent, writes the shim next to `transcrypt` only when it is
missing or the real openssl has moved, and prints the path it wired. See the warning's own section below
for why the shim redirects rather than fixing the KDF.

Doppler's auth is **directory-scoped**, so read the key from a scoped directory. Fetching it from an
unscoped path (a temp dir, say) fails with "you must provide a token" and transcrypt then dies on an
empty password — capture the key into a variable before changing directories if the init runs elsewhere.

Init also refuses on a **dirty tree** — if a tracked file is modified, stash just it first
(`git stash push <file>`), init, then `git stash pop`. Untracked files don't block it.

**Init in a repo that ALREADY has encrypted files decrypts them, and may leave them permanently modified.**
That is mode B happening as a side effect, and it is expected. What is not obvious: transcrypt may then
re-encrypt to *different ciphertext than what is committed*, so the files show as ` M` forever until
somebody commits the re-encryption. Transcrypt's salt is derived from the content, so this is not random —
it is stable across runs and reflects a different transcrypt or openssl version having written the original.
Init also prints `Unexpected new dirty files in the repository … please check your password`, which reads
like a wrong key and usually is not.

Diagnose before believing either reading, and diagnose by **content, not by ciphertext**:

```
git show ":$F" | "$(git rev-parse --git-common-dir)/crypt/transcrypt" smudge context=default "$F" | diff - "$F"
```

Identical output means the key is right and only the representation differs. Do **not** commit that churn
as part of an unrelated change — it is a content-free diff, and if another machine re-churns it back the two
will ping-pong. Raise it as its own decision.

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

Install it into a directory that is **already on PATH** — check first rather than assuming `~/bin`, which
exists on some machines without being on PATH, leaving a downloaded file nothing can run:

```
D=$(for d in ~/.local/bin ~/bin /usr/local/bin; do case ":$PATH:" in *":$d:"*) echo "$d"; break;; esac; done)
curl -fsSL https://raw.githubusercontent.com/elasticdog/transcrypt/main/transcrypt -o "$D/transcrypt" && chmod +x "$D/transcrypt" && hash -r
``` **Classifier caveat:** the auto-mode classifier may
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

   **Do NOT rename when something outside the repo reads the file by name.** The filename is then part of
   an interface, and renaming breaks the thing the file configures — grepping the repo will not save you,
   because the reference lives in the caller. Mark the path explicitly instead, and record in a comment
   why it departs from the convention:
   ```
   config/publish.env filter=crypt diff=crypt merge=crypt
   ```
   The real case: the shared publish script reads `config/publish.env` at that exact path, so
   `publish.secret.env` would break every publish on every machine and there is nothing in the repo to
   update. Encrypt-by-path is correct there. The naming convention is the default, not the requirement.
4. Stage so the clean filter encrypts it: `git add .gitattributes <the target>`.
5. **Verify** — the index blob must be ciphertext while the working tree stays plaintext. Follow
   `~/.claude/learnings/transcrypt-verify-before-commit.md` and run the assertions it gives; do not
   retype them from memory or paraphrase them into a message. That learning exists because the obvious
   check is wrong in a specific way: the ciphertext's base64 begins `U2FsdGVkX1` and the **eleventh**
   character encodes salt bits, so an assertion pinning it (`U2FsdGVkX1+`) passes about a quarter of the
   time and cries "plaintext!" over a perfectly good blob. Decode instead of prefix-matching, and prefer
   a smudge round-trip, which also catches a wrong key. If the index really does show plaintext, **STOP**
   — the filter didn't run (transcrypt not initialized, or the `.gitattributes` pattern doesn't match).
   Fix before anything is committed.
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
- Do **not** run `transcrypt init` in a DEPLOY CHECKOUT — a server's clone of the repo, a CI workspace, or
  anything reconciled by `git reset --hard`. Init sets `filter.crypt.required=true`, which turns every future
  checkout there into a **hard failure** without the key; and the key must never be on such a box, because it
  decrypts every transcrypted file in every repo, not just the one in front of you. Left un-initialized, an
  encrypted file simply checks out as inert ciphertext that nothing on the box reads — clone succeeds,
  content passes through untouched. That state looks accidental and is correct: do not "fix" it. If a server
  genuinely needs a decrypted value, render it there from Doppler instead.

## Pre-commit safety net (already global)

A guarded transcrypt pre-commit hook is installed globally (`~/.git-hooks/pre-commit` via
`core.hooksPath`, tracked in the dotfiles repo). It blocks committing a `*.secret.*` file that lacks the
encrypted "Salted" magic, and no-ops in non-transcrypt repos. So **ignore transcrypt's "manually install
the pre-commit script" message** if you ever see it — the global hook already covers every repo; no
per-repo hook install is needed. The `core.hooksPath` bracket in the shared-key section keeps transcrypt's
own copy inside `.git/hooks/`, so that message should not appear at all.

## The `deprecated key derivation` warning — silence it, do not "fix" it

Once a repo has a crypt filter, git prints this on `git status`, `git add`, `git diff` — anything that has to
hash a filtered file:

```
*** WARNING : deprecated key derivation used.
Using -iter or -pbkdf2 would be better.
```

**It is not a sign of misconfiguration.** Transcrypt invokes `openssl enc … -md MD5`, and OpenSSL ≥ 1.1.1
warns whenever `enc` runs without `-pbkdf2`/`-iter`. Git passes filter stderr straight through, so the notice
surfaces on ordinary commands. Nothing is wrong.

**Do not try to switch the KDF.** Verified against upstream `main` (transcrypt 2.3.3-pre): `-md MD5` is
hardcoded in all four `openssl enc` call sites, the only git-config knobs are `cipher`, `crypt-dir`,
`openssl-path`, `password` and `version`, and `pbkdf2` appears nowhere in the script. Upstream has tracked
this since 2019 without merging a fix — [#55](https://github.com/elasticdog/transcrypt/issues/55) (the
warning), [#59](https://github.com/elasticdog/transcrypt/issues/59) (asking for `-pbkdf2 -iter 1024`), and
[#203](https://github.com/elasticdog/transcrypt/issues/203) (a patch using runtime feature detection, since
older OpenSSL rejects the flag). Patching it locally means every machine needs the patched build forever, and
a machine that reinstalls stock transcrypt then **cannot decrypt** what the patched one wrote — presenting as
a wrong-key error rather than a wrong-tool error.

**And the benefit would be nil here.** A slow KDF protects a *guessable* passphrase. `TRANSCRYPT_KEY` is a
64-character random value, so guessing is infeasible regardless of derivation cost. This changes only if the
passphrase is ever replaced with something memorable — that is the condition to watch, not the warning.

**It is silenced by redirecting openssl, not by touching the crypto** — and the shared-key sequence above
already does it, so there is nothing to decide here. Transcrypt supports `transcrypt.openssl-path`
([#108](https://github.com/elasticdog/transcrypt/issues/108)) precisely for this, and
`scripts/ensure-openssl-shim.sh` writes a shim that filters the two lines from stderr and changes nothing
else, then prints its path for the `git config --local` that wires it.

What the generated shim does, since the reasoning matters more than the file:

```sh
exec 3>&1                         # stdout on fd 3 — binary ciphertext passes through unaltered
err="$("$REAL" "$@" 2>&1 1>&3)"
rc=$?                             # openssl's status, not the filter's
exec 3>&-
[ -n "$err" ] && printf '%s\n' "$err" | grep -vE '<the two warning lines>' >&2
exit $rc
```

Route stdout through fd 3 rather than a shell variable, or binary output gets mangled. Per repo and per
machine, nothing committed, ciphering untouched — blobs stay byte-compatible with a machine running stock
transcrypt, which is the whole reason for redirecting rather than patching.

Two things the helper handles that a hand-rolled shim gets wrong: it resolves the real openssl by walking
`PATH` itself, because `command -v -a` is a bashism that yields nothing under a POSIX `sh`; and it skips any
candidate that is itself a shim, or a second run once the shim is on `PATH` points it at itself and recurses
until the stack gives out.

**Never `git config --unset transcrypt.openssl-path`.** It reads like reverting to a default and is not —
there is no default. The clean, smudge and textconv filters all resolve openssl as
`openssl_path=$(git config --get --local transcrypt.openssl-path)` with **no fallback**, then invoke
`"$openssl_path" enc …`; unset, that expands to the empty string and every filtered file dies with
`fatal: <file>: clean filter 'crypt' failed`. `transcrypt init` always writes the key (its last line is
`git config transcrypt.openssl-path "$openssl_path"`), so the setting is required infrastructure and the
sequence's fourth line *replaces* it rather than adding anything. To go back to unshimmed openssl, point it
at the real binary — do not remove it.

Beware of testing this with `git status` alone: git skips the filter entirely when its stat cache says the
file is untouched, so an unwired repo can look silent. `touch` the encrypted file first to force a re-hash.

**The warning is worth silencing for a reason beyond tidiness:** it pollutes stderr, and it has already
crowded out the result of a real check, making a test that asserted nothing look like it had passed. Anything
scripted around these files should assert on **exit status**, never on output text.

## Fresh-machine note

On any new clone, `*.secret.*` files stay ciphertext until mode **B** runs once. The `.gitattributes` and the
encrypted blobs are committed; the key is not — it lives only in Doppler.
