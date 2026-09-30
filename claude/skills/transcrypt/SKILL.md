---
name: transcrypt
description: >-
  Encrypt files in a git repo with transcrypt using the shared Doppler-stored passphrase, or unlock
  (decrypt) an already-encrypted repo after a fresh clone, or rotate the shared passphrase across repos.
  Designated files stay plaintext in the working tree but are stored encrypted in git history.
  TRIGGER when: the user wants to commit a file encrypted, protect a sensitive committed doc, set up
  transcrypt in a repo, decrypt/unlock secret files after cloning, or rotate/rekey the shared key.
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
- this repo's transcrypt config: !`git config --name-only --get-regexp '^transcrypt\.' 2>/dev/null || echo NOT-CONFIGURED`
- encrypt attribute in .gitattributes: !`test -f .gitattributes && grep -i crypt .gitattributes || echo NONE`
- working tree: !`git status --short 2>/dev/null || echo "(not a git repo)"`
- openssl shim wired: !`git config --get transcrypt.openssl-path 2>/dev/null || echo "none — expect the 'deprecated key derivation' warning on git commands; see that section"`

## The shared key — never generate a new one

Every init/unlock uses the Doppler-stored passphrase and `aes-256-cbc` (the standard cipher for these
repos). This one sequence is referenced throughout; the key is never printed. Run it from the repo root,
and keep every line; the bracket around the middle one is explained below:

```
git config core.hooksPath "$(git rev-parse --path-format=absolute --git-common-dir)/hooks"
transcrypt -c aes-256-cbc -p "$(doppler secrets get TRANSCRYPT_KEY --project tools --config prd --plain)" -y
git config --unset core.hooksPath
SHIM=$(sh ~/.claude/skills/transcrypt/scripts/ensure-openssl-shim.sh) || SHIM=
[ -n "$SHIM" ] && git config --local transcrypt.openssl-path "$SHIM" || echo "shim not wired: openssl-path left as transcrypt init wrote it" >&2
```

**Run it as plain lines, not wrapped in a `bash <<'EOF'` heredoc.** On 2026-09-29 auto mode denied this
sequence in heredoc form and allowed the same commands written plainly, so a denial of the wrapped form is
about the heredoc, not about transcrypt, and the classifier notes under Step 0 and mode C do not explain it.

**Run the `--unset` line even when the transcrypt line fails or is refused.** A
local `core.hooksPath` left behind points git at `.git/hooks`, where at most transcrypt's own helper runs,
and switches the global hook off in that repo without a word — its `publish.env` check and its
whole-shape ciphertext check included; the helper reads only a file's first eight bytes. Afterwards
`git config --local --get core.hooksPath` must print nothing; never chain the three lines with `&&`.

The shim wiring at the end silences OpenSSL's `deprecated key derivation` warning, which every crypt filter otherwise
prints on `git status`, `git add` and `git diff` for the life of the repo. It is part of the sequence rather
than an optional extra because the warning is pure noise that has already crowded out the result of a real
check, and because **`init` and `--rekey` both rewrite `transcrypt.openssl-path`** — so anything that re-inits
or rekeys has to re-apply it anyway. The helper is idempotent, writes the shim next to `transcrypt` only when it is
missing or the real openssl has moved, and prints the path it wired. See the warning's own section below
for why the shim redirects rather than fixing the KDF.

**The capture is guarded because an unguarded one can brick the repo.** When the generator fails, `$( )`
expands to the empty string, so a bare `git config … "$( … )"` writes an **empty** `openssl-path`. That is
worse than an unset one: `git config --get` then exits 0 and prints nothing, so even the two read sites
carrying a `|| printf` fallback accept the empty value, and every one of the five resolution points below
breaks rather than three. What you see is `fatal: <file>: clean filter 'crypt' failed` on every filtered
file, while the generator's own stderr has already scrolled past above the assignment and reads as the
generator's problem rather than the config write's. Hence both arms: `|| SHIM=` catches a generator that
exits non-zero, and the `-n` test catches one that exits 0 having printed no path. Since clean, smudge and
textconv have no fallback, this is the one command in the setup that can take a repo down.

Doppler's auth is **directory-scoped**, so read the key from a scoped directory. Fetching it from an
unscoped path (a temp dir, say) fails with "you must provide a token" and transcrypt then dies on an
empty password — capture the key into a variable before changing directories if the init runs elsewhere.

Init also refuses on a **dirty tree** — if a tracked file is modified, stash just it first
(`git stash push <file>`), init, then `git stash pop`. Untracked files don't block it.

**Init writes the passphrase into `.git/config` in plaintext, as `transcrypt.password`**, so never print
that file or list it: `git config --list`, `cat .git/config`, a Read of it and `transcrypt --display` all
show the key, and `hooks/secret-print-guard.py` refuses each of them. It cannot be moved out through
`include.path`: transcrypt reads it with `git config --get --local`, and git ignores includes when a
single scope is named. To check whether a repo is set up, list names only:
`git config --name-only --get-regexp '^transcrypt\.'`.

**Init in a repo that ALREADY has encrypted files decrypts them, and may leave them permanently modified.**
That is mode B happening as a side effect, and it is expected. What is not obvious: transcrypt may then
re-encrypt to *different ciphertext than what is committed*, so the files show as ` M` forever until
somebody commits the re-encryption. Transcrypt's salt is derived from the content, so this is not random —
it is stable across runs. A different transcrypt or openssl version can cause it, but the far more common
cause is line endings; see "A secret file that is permanently modified" below before believing anything else.
Init also prints `Unexpected new dirty files in the repository … please check your password`, which reads
like a wrong key. Outside a key rotation it usually is not one, but during a rotation it may be exactly that.

Diagnose before believing either reading. First confirm the key opens the blob at all, by openssl's exit status.
The command is in `~/.claude/learnings/transcrypt-verify-before-commit.md`, under "A wrong key passes the round
trip". The content check below cannot do it: a wrong key leaves garbage followed by the raw ciphertext in the
working tree, and smudging the blob again reproduces those same bytes. With the key confirmed, diagnose by
**content, not by ciphertext**:

```
git show ":$F" | "$(git rev-parse --git-common-dir)/crypt/transcrypt" smudge context=default "$F" | diff - "$F"
```

Identical output then means only the representation differs. Do **not** commit that churn
as part of an unrelated change — it is a content-free diff, and if another machine re-churns it back the two
will ping-pong. Committing it once does not settle it. Find the cause instead — it is almost always the
line-ending one below, and that one has a one-line fix.

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
```

**Classifier caveat:** the auto-mode classifier may block *executing* transcrypt the first time (it is a
fetched script). A classifier refusal carries no permission prompt to approve, and no allow rule is a
verified remedy (see mode C step 3). Take the refusal to the user — do **not** work around the denial.

## Pick the mode

From Context and the user's request:

- **Encrypt a file** — the user named a file/doc to protect → do **A**.
- **Unlock after clone** — **encrypt attribute** shows `crypt` but **this repo's transcrypt config** is
  `NOT-CONFIGURED` (secret files read as ciphertext locally) → do **B**.
- **Setup only** — the user wants transcrypt ready with no file yet → run A step 1, then stop.
- **Rotate the key** — the shared passphrase leaked or must change, or a rotation is under way and this
  repo has not followed it yet → do **C**.

## A — Encrypt a file

1. If **this repo's transcrypt config** is `NOT-CONFIGURED`, initialize with the shared-key sequence above.
2. Ensure `.gitattributes` carries the encrypt pattern; add this line if missing (**encrypt attribute** is
   `NONE`):
   ```
   *.secret.* filter=crypt diff=crypt merge=crypt text=auto eol=lf
   ```
   Do **not** add `-text` here, and do **not** leave the line-ending attributes off. Transcrypt stores base64,
   which is text — marking it binary disables git's line-ending normalization, so a Windows clone commits
   CRLF-wrapped ciphertext and a macOS/Linux clone rewrites it to LF, churning the file on every
   cross-platform round trip. Writing `text=auto eol=lf` out in full normalizes the ciphertext whatever a
   given clone sets `core.autocrlf` to; omitting it merely borrows a global `* text=auto eol=lf`, which is
   per-machine, uncommitted, and absent on CI. Keep `auto` rather than a bare `text`, so a genuinely binary
   secret that matches the pattern one day is still safe (see `~/.claude/learnings/git-line-endings.md`).
   Upstream's own `transcrypt --add` writes the bare line — it has no Windows story, so do not "correct"
   this back to match it.

   **If the pattern is already there but carries `-text`, that is the bug, not a style difference** — it is
   the form this skill prescribed before 2026-08. Repair it with "A secret file that is permanently modified"
   below rather than leaving it.
3. Ensure the target matches the pattern. If it isn't already `*.secret.*`, rename it —
   `mv <dir>/<name>.<ext> <dir>/<name>.secret.<ext>` — and update any references to the old name (grep the
   repo).

   **Do NOT rename when something outside the repo reads the file by name.** The filename is then part of
   an interface, and renaming breaks the thing the file configures — grepping the repo will not save you,
   because the reference lives in the caller. Mark the path explicitly instead, and record in a comment
   why it departs from the convention:
   ```
   config/publish.env filter=crypt diff=crypt merge=crypt text=auto eol=lf
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
   a smudge round-trip. It proves the blob decrypts back to the file under the key this clone holds, but not
   that this is Doppler's key. The learning's openssl exit-status test proves that. If the index really does show plaintext, **STOP**
   — the filter didn't run (transcrypt not initialized, or the `.gitattributes` pattern doesn't match).
   Fix before anything is committed.
6. Do **not** commit. Report that the file is staged, encrypted, and ready; the commit happens via `/commit`
   with the rest of the change set.

## B — Unlock a repo after clone

Secret files read as ciphertext because transcrypt isn't configured on this machine yet. Run the shared-key
sequence above; transcrypt decrypts every `*.secret.*` file in place. Confirm with a clean `git status --short`
and `head -1 <a .secret file>` (readable plaintext). A wrong key lists each file as ` M`, holding garbage followed
by the raw ciphertext, and init warns `please check your password`.

## C — Rotate the key

One passphrase encrypts every repo, so a rotation reaches all of them. The new key is generated once. Then, in each
repo holding encrypted files, exactly one clone rekeys and pushes, and every other clone of that repo follows the
rekey rather than repeating it. The rekey belongs to a session working in that repo, which takes the commit and the
push to its user. Blobs already in history stay encrypted under the old key. A rotation protects what is committed
from then on, and anyone holding the old key can still read what history holds.

1. **Find a set-up clone of every repo that needs the rekey.** When a rotation is already under way, measure which
   repos those are before asking anyone to rekey. Being set up and holding encrypted files says nothing about which
   key the blobs are under. Decrypt each repo's origin blobs with Doppler's key and assert openssl's exit status,
   using the command in `~/.claude/learnings/transcrypt-verify-before-commit.md`. A repo that passes is already
   rotated. A second rekey there, from a clone still on the old key, makes a commit that conflicts with the one on
   origin.

   A rekey decrypts with the current key, so it runs only in a clone that already has it. A fresh clone, or a
   flushed one, cannot rekey. Each set-up clone keeps its own copy of the key in `.git/config`, so the old key
   survives there after Doppler moves on. When no clone of a repo holds it, stop and ask the user where the old
   value can come from, since Doppler may still have it in the secret's history. Leave every clone of that repo
   locked meanwhile. In a set-up clone, `transcrypt --list` names the repo's encrypted files. A repo that is set up
   but holds none needs no rekey: run step 6 in each of its clones, minus the pull, so that the next file it
   encrypts uses the new key.
2. **Generate the new key into Doppler.** Do this only when the user has asked for a rotation, and run it from a
   directory Doppler is scoped to. The key goes in on stdin and is checked by comparison, never printed:
   ```
   NEW=$(openssl rand -hex 32) && [ ${#NEW} -eq 64 ] && printf '%s' "$NEW" | doppler secrets set TRANSCRYPT_KEY -p tools -c prd --silent && BACK=$(doppler secrets get TRANSCRYPT_KEY -p tools -c prd --plain) && if [ "$NEW" = "$BACK" ]; then echo "stored and read back: match (len ${#BACK})"; else echo "MISMATCH (stored len ${#BACK})"; fi; unset NEW BACK
   ```
3. **Rekey in the set-up clone**, on a clean tree that is up to date with its remote:
   ```
   transcrypt --rekey -c aes-256-cbc -p "$(doppler secrets get TRANSCRYPT_KEY --project tools --config prd --plain)" -y
   SHIM=$(sh ~/.claude/skills/transcrypt/scripts/ensure-openssl-shim.sh) || SHIM=
   [ -n "$SHIM" ] && git config --local transcrypt.openssl-path "$SHIM" || echo "shim not wired: openssl-path left as transcrypt init wrote it" >&2
   ```
   The shim wiring is there for the reason given under the shared-key sequence: a rekey saves its
   configuration through the same code as init, so it rewrites the helper script and `transcrypt.openssl-path`
   too. It skips the helper hooks, so it needs no `core.hooksPath` bracket. It re-encrypts every encrypted file and stages it, so each one reads `M `. Auto mode can refuse
   `transcrypt --rekey` outright, with no prompt. In the 2026-09-29 rotation it refused in some clones and ran
   in others, and in one clone ran after earlier refusals, with nothing written to any settings file. This
   skill's own `allowed-tools` lists `Bash(transcrypt:*)` while it is loaded, but the sequence also runs
   `sh`, which that list does not cover. No grant was found, so the verdict on an unchanged command is not stable,
   and a refusal in one clone predicts nothing about another. Take the refusal to the user and do not route
   around it. An allow rule such as `Bash(transcrypt:*)` is not a verified remedy.
4. **Verify from the index, not from a diff:**
   ```
   C="$(git rev-parse --git-common-dir)/crypt/transcrypt"
   echo "$(transcrypt --list | wc -l) encrypted files"
   transcrypt --list | while IFS= read -r F; do
     [ "$(git rev-parse ":$F")" != "$(git rev-parse "HEAD:$F")" ] || echo "not rekeyed: $F"
     [ "$(git cat-file -p ":$F" | head -c 10)" = U2FsdGVkX1 ] || echo "not ciphertext: $F"
     git cat-file -p ":$F" | "$C" smudge context=default "$F" | cmp -s - "$F" || echo "round-trip differs: $F"
   done
   ```
   Silence under the count means every file passed, and a count of 0 means nothing was checked. Do not judge the
   rekey by `git diff`. The crypt textconv decrypts the new blob and prints the old one raw, so a plain `git diff`
   emits the file's plaintext, and `--stat` reports `0 insertions(+), 0 deletions(-)`, which looks like a change
   with nothing in it. To see the ciphertext, use `git diff --no-textconv`. The mechanism is in
   `~/.claude/learnings/transcrypt-verify-before-commit.md`, under verifying a rekey.
5. **Commit the rekey on its own and push it.** Any `git reset HEAD` throws the rekey's staging away, and
   `/commit` runs one in its Context. Re-stage each encrypted file with a plain `git add` before the commit. The
   ciphertext is deterministic, so that reproduces the identical blob. Run the loop again: it reports
   `not rekeyed` until the staging is back.
6. **In every other clone of that repo, once the rekey is on origin, flush, then pull, then set up.** Until then,
   leave the clone alone. The shared-key sequence reads the new key, which cannot open old-key blobs, so unlocking
   early fills each encrypted file with garbage followed by the raw ciphertext. Start from a clean tree with nothing
   unpushed:
   ```
   transcrypt --flush-credentials -y
   git pull --ff-only
   ```
   Then run the shared-key sequence above, which now reads the new key, and confirm as in B. The flush removes the
   old key and the filter, and checks the encrypted files out as ciphertext, so the pull brings in the new
   ciphertext without decrypting it. A clone that was never set up has nothing to flush: pull, then run the
   sequence.

   Two kinds of local change block the pull. An untracked per-machine copy at an encrypted path, such as a
   `config/publish.env` kept from before that file was encrypted, makes git refuse it. Move the copy into `.git/`,
   pull and unlock, then compare it with the committed file by key name without printing any value. Delete it once
   the user agrees. A local edit to a file the incoming commits also change goes into a stash of that one path,
   popped after the unlock.
7. **A clone that pulled before flushing** decrypts the new ciphertext with its old key. Its encrypted files then
   read ` M` and hold garbage. Do not commit or stash that ` M`, because the working copy is not the file's
   content. Neither obvious fix works. `transcrypt --flush-credentials` refuses with `the repo is dirty`, and
   `git checkout -- <file>` decrypts with the old key again. Drop the filter so that the files check out as raw
   ciphertext, then flush:
   ```
   git config --remove-section filter.crypt
   transcrypt --list | while IFS= read -r F; do git checkout -- "$F"; done
   transcrypt --flush-credentials -y
   ```
   Then run the shared-key sequence. This was reproduced on 2026-09-29 with fake keys in a scratch repo. Step 6's
   order ended on a clean tree with readable plaintext. Pulling first ended where this step starts, and this
   recovery ended clean.

## Out of scope

- Do **not** commit or push — staging + verify only; `/commit` owns the commit.
- Do **not** generate a new passphrase — always the Doppler `TRANSCRYPT_KEY`. The one exception is mode C, and only
  when the user has asked for a rotation.
- Do **not** put env-style secrets (keys, tokens, passwords) in committed files — those belong in Doppler.
- Do **not** work around a classifier denial on executing transcrypt — take it to the user.
- Do **not** run `transcrypt init` in a DEPLOY CHECKOUT — a server's clone of the repo, a CI workspace, or
  anything reconciled by `git reset --hard`. Init sets `filter.crypt.required=true`, which turns every future
  checkout there into a **hard failure** without the key; and the key must never be on such a box, because it
  decrypts every transcrypted file in every repo, not just the one in front of you. Left un-initialized, an
  encrypted file simply checks out as inert ciphertext that nothing on the box reads — clone succeeds,
  content passes through untouched. That state looks accidental and is correct: do not "fix" it. If a server
  genuinely needs a decrypted value, render it there from Doppler instead.

## Pre-commit safety net (already global)

A pre-commit hook is installed globally (`~/.git-hooks/pre-commit` via `core.hooksPath`, tracked in the
dotfiles repo). Its ciphertext check refuses a commit while any file marked `filter=crypt` sits in the index
as anything but transcrypt's output, and does nothing in a repo that marks no file. In every clone it
checks each blob's whole shape, not its first bytes: transcrypt's own check reads eight bytes, and its
clean filter passes a file that already opens with the magic through unchanged, so ciphertext with a line
appended would satisfy both. In a clone that is not unlocked — never set up, or flushed — the hook's
reading is the only check: git ignores the unconfigured filter there, so a secret rewritten before mode B
stages as plaintext, and the working copy is the ciphertext itself. Where the clone is unlocked,
transcrypt's check runs after the hook's, so plaintext already in history gets the hook's warning to
rewrite it and rotate the value. Its reach stops here:

- Rebase, `am`, cherry-pick, revert and a merge that needs no resolution (a pull included) commit without
  running pre-commit, so a plaintext secret they carry in is refused at the next ordinary commit, not at
  the one that made it.
- A repo-local `core.hooksPath` replaces the global one, so the hook does not run in that repo at all —
  which is why the shared-key bracket must always reach its `--unset` line.
- The hook's own reading covers the default context only, in every clone. A file marked `crypt-<name>`
  gets transcrypt's eight-byte check where the clone is unlocked and no check where it is not. This skill
  never creates a named context.
- Text appended after a ciphertext whose last line is already full passes when it is itself base64 of
  whole AES blocks — `openssl rand -base64 16`, `32` or `48` output, say — unless a line of it is all hex.
- Which files are marked comes from the working tree's `.gitattributes`, as for `git add`, so an unstaged
  edit that drops a file's marking hides that file from the check.

So **ignore transcrypt's "manually install the pre-commit script" message** if you ever see it — the
global hook covers every repo that does not override `core.hooksPath`; no per-repo hook install is needed.
The `core.hooksPath` bracket in the shared-key section keeps transcrypt's own copy inside `.git/hooks/`,
so that message should not appear at all.

## A secret file that is permanently modified — suspect line endings first

Symptom: one `*.secret.*` file shows ` M` on an otherwise clean tree, forever. The decrypt-and-diff above
says the content is identical, `git diff` shows nothing useful because git renders filtered files as `Bin`,
and committing the churn only hands it to the other machine, which hands it straight back.

**The cause is almost always `-text` on the crypt rule, not a version difference.** Transcrypt's stored form
is base64, and the Windows-native openssl that Git Bash puts on PATH (`/mingw64/bin/openssl`) terminates its
base64 lines with CRLF where macOS and Linux use LF. Git would normalize that away on the way into the blob,
except `-text` declares the path binary and short-circuits eol conversion entirely — so each machine stores
its own line endings and rewrites the other's. Confirm it without changing anything:

```
F=<the file>; C="$(git rev-parse --git-common-dir)/crypt/transcrypt"
echo "clean output: $("$C" clean context=default "$F" < "$F" | tr -cd '\r' | wc -c) CRs"
echo "stored blob:  $(git cat-file -p HEAD:"$F" | tr -cd '\r' | wc -c) CRs"
```

Different CR counts, with a byte-size delta equal to the line count, is line endings and nothing else. Prove
no content is at stake by stripping the CRs and hashing — it reproduces the stored blob exactly:

```
"$C" clean context=default "$F" < "$F" | tr -d '\r' | git hash-object --stdin   # == git rev-parse HEAD:$F
```

The repair is on the rule, not on the file:

1. Give every `filter=crypt` line `text=auto eol=lf`, replacing `-text` where it appears.
2. Re-stage with `git add --renormalize <the file>`. Skipping this is safe only when the stored blob already
   happens to be the LF one: `text=auto` declines to convert a file that is *already in git with CRLF
   endings*, so without the renormalize the fix can silently do nothing.
3. Confirm the file went clean — `git status --short` should list only `.gitattributes`.

Then sweep the other repos, because this guidance changed in 2026-08 and anything set up before then has the
old form baked in. That sweep is what was missed the first time, which left one repo churning for weeks:

```
grep -rl --include=.gitattributes --exclude-dir=node_modules 'filter=crypt' <projects-root> \
  | xargs grep -n 'filter=crypt.*-text'
```

Do **not** try to fix this inside transcrypt. Patching the vendored script to strip CR does nothing — git
runs the untracked per-clone copy under `.git/crypt/`, never the copy tracked in the repo — and that exact
fix was tried here once and silently never executed. Repointing `transcrypt.openssl-path` at the msys
`/usr/bin/openssl`, which emits LF, does work but only on the machine that sets it. Upstream has no position
to defer to: it has never recommended `-text` in any version, and its tracker has nothing on CRLF ciphertext.

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
there is no default *on the paths that matter*. transcrypt resolves openssl in five places, and they do not agree:
lines 229 and 1021 end in `|| printf '%s' "$openssl_path"` and survive an unset, which is why init still works and
why the breakage looks intermittent. The three that have **no fallback** are the ones git actually calls — clean,
smudge and textconv (lines 290, 315, 332) — each resolving it as
`openssl_path=$(git config --get --local transcrypt.openssl-path)` and then invoking
`"$openssl_path" enc …`; unset, that expands to the empty string and every filtered file dies with
`fatal: <file>: clean filter 'crypt' failed`.

Two more sites settle *why* the key is infrastructure rather than an optional tweak — it is **written**
unconditionally in two places: `save_configuration` (line 723), which both `init` and `--rekey` reach, and the
`--set-openssl-path=` argument handler (line 1535):

```
229   read,  falls back        290/315/332   read, NO fallback  (clean, smudge, textconv)
1021  read,  falls back        723/1535      WRITE  (save_configuration, --set-openssl-path)
```

**Re-wire the shim after every `--rekey`, not only after an init.** A rekey reaches that same write and puts
the built-in `openssl` default there, discarding the configured path; `--upgrade` is the only mode that reads
the old value back. The mechanism is in `~/.claude/learnings/transcrypt-verify-before-commit.md`, under
verifying a rekey.

So a repo cannot arrive at an *unset* key by itself; only a hand `--unset` gets it there. It can arrive at an
**empty** one by itself, from an unguarded `git config … "$(generator)"` whose generator died, which is why the
shared-key sequence above guards that capture. Empty deserves its own check rather than being read as a flavour
of unset, because it defeats the two fallbacks an unset survives. Either way the entry is not redundant, and that
is what stops the next person tidying it away. The shared-key sequence's shim wiring *replaces* what init wrote
rather than adding anything. To go back to unshimmed openssl, point it at the real binary; do not remove it.

Beware of testing this with `git status` alone: git skips the filter entirely when its stat cache says the
file is untouched, so an unwired repo can look silent. `touch` the encrypted file first to force a re-hash.

**The warning is worth silencing for a reason beyond tidiness:** it pollutes stderr, and it has already
crowded out the result of a real check, making a test that asserted nothing look like it had passed. Anything
scripted around these files should assert on **exit status**, never on output text.

## Fresh-machine note

On any new clone, `*.secret.*` files stay ciphertext until mode **B** runs once. The `.gitattributes` and the
encrypted blobs are committed; the key is not — it lives only in Doppler.
