# Proving a transcrypt file will actually encrypt

Files matched by a `filter=crypt` rule in `.gitattributes` stay plaintext in the working tree and are stored
encrypted. That split is the point, and it is also why a mistake is invisible: the file you read looks correct
whether or not the filter is wired, and you find out it was not at push time, in a public repo.

Check before committing, not after.

## The three things to check

```bash
# 1. does the path actually match a crypt rule?
git check-attr filter diff merge -- <path>        # want: filter: crypt

# 2. is transcrypt initialised in THIS clone? (a fresh clone is not, until unlocked)
git config --get filter.crypt.clean               # empty means the rule matches nothing

# 3. what will git actually store?
```

Steps 1 and 2 are independent: a path can match `filter=crypt` while the clone has no `filter.crypt.clean`
configured, in which case git stores the plaintext and reports no error.

## Step 3, and the `%f` trap

Do not do this — `git config` returns the filter with a literal `%f` placeholder that git substitutes per file,
and a shell `eval` leaves it unsubstituted:

```bash
eval "$(git config --get filter.crypt.clean)" < file   # WRONG: %f never expands
```

It produces **empty output**, and empty output trivially contains no secrets. So a `grep` for your secret over
that result reports "clean" and proves nothing whatsoever. Substitute the filename yourself:

```bash
CRYPT_DIR="$(git config transcrypt.crypt-dir 2>/dev/null || printf '%s/crypt' "$(git rev-parse --git-common-dir)")"
"$CRYPT_DIR/transcrypt" clean context=default "$F" < "$F" | head -c 120
```

Correct output starts with the OpenSSL base64 marker `U2FsdGVkX1...` ("Salted__"). Anything readable means the
file is about to be committed in the clear. An `openssl` deprecation warning on stderr is normal and not a
failure.

**Pass the file's own name — the filename is an input to the cipher, not just a `%f` mechanic.** Transcrypt
derives each file's salt from an HMAC keyed with `<filename>:<password>`, so a wrong name does not fail: it
encrypts successfully to a *different, valid-looking* blob. Two consequences follow. Comparing a file under
another path's attributes (`git hash-object --path=<other> <file>`) is not a control — it returns a third hash
matching neither side, which reads as a difference that is not there. And renaming a tracked secret re-encrypts
it wholesale, so the rename lands as a full-content change containing no content change at all.

**Run the helper with the shell's cwd inside the repo being checked.** Transcrypt resolves its password with
`git config`, so a helper started from another checkout silently uses *that* checkout's key. Measured 2026-09-28
during a key rotation: a survey run from the dotfiles checkout reported four repos as mismatched, and the clean
filter had returned empty output, hashing to the empty blob `e69de29`, instead of failing.

Run that command under **bash**. The string `git config` hands back contains nested `""$(...)""` quoting, and
zsh evaluates it differently — producing empty output and exit 0, the same silent, secret-free-looking result
as the `%f` trap, for an unrelated reason. Two shells, one indistinguishable false pass.

### Stop the prefix at 10 characters

`U2FsdGVkX1` is the longest prefix that is always true. The 11th base64 character encodes the top two bits of
the **first salt byte**, so all four of these are correct OpenSSL output:

| first salt byte | prefix |
| --- | --- |
| `0x00` | `U2FsdGVkX18…` |
| `0x40` | `U2FsdGVkX19…` |
| `0x80` | `U2FsdGVkX1+…` |
| `0xC0` | `U2FsdGVkX1/…` |

A check pinning one of them — `[ "$prefix" = "U2FsdGVkX1+" ]` — passes about a quarter of the time and calls
correct ciphertext plaintext the rest. Worse, transcrypt derives the salt by HMAC **over the file's contents**,
so editing one comment changes that character: the same file, repo and key produced `U2FsdGVkX18A` before an
edit and `U2FsdGVkX1+…` after. A rule "verified working" on one machine can fail on the next commit of the
same file, which reads as a broken filter rather than a broken check.

Compare 10 characters, or skip the guessing and decode.

Then assert the negative on the *stored* form, not the working-tree form:

```bash
OUT=$("$CRYPT_DIR/transcrypt" clean context=default "$F" < "$F")
printf '%s' "$OUT" | grep -qiE "<secret>|<hostname>|<username>" && echo LEAK || echo clean
```

## Ask git what it stored, and beware that `git show` decrypts

Running the filter by hand proves the filter works. It does not prove git *used* it. Once the file is staged,
read the index; once committed, read the object — that is the artifact that becomes permanent:

```bash
git add <path>
git show :<path> | head -c 10                 # index blob   -> U2FsdGVkX1
git cat-file -p HEAD:<path> | head -c 10      # stored blob  -> U2FsdGVkX1
git cat-file -s "$(git rev-parse HEAD:<path>)"  # size, so an empty read cannot pass
```

**Do not verify with `git show HEAD:<path>`.** A `diff=crypt` attribute installs a textconv, and `git show`
helpfully runs it — printing the *decrypted* file while the repo holds ciphertext. It looks exactly like the
leak you are checking for, so the natural reaction is to panic and "fix" a working setup. `git cat-file -p`
applies no filters and is the honest reader. (The inverse also misleads: `git show --stat` reports the file as
`Bin 0 -> N bytes` with 0 insertions, which is normal for ciphertext, not a sign the content is missing.)

The strongest single assertion is a round-trip — decrypt the stored blob and diff it against the working tree:

```bash
git cat-file -p HEAD:<path> | "$CRYPT_DIR/transcrypt" smudge context=default | diff - <path>
```

It proves the stored blob and the working tree agree under whatever key the clone holds. It says nothing about
whether that key is the right one, as the next section shows.

## A wrong key passes the round trip

Measured 2026-09-29, on a scratch repo unlocked with the wrong key, the round trip above passed. `openssl enc -d`
writes its partial output before the padding check fails, and transcrypt's smudge then appends the raw
ciphertext (`… 2>/dev/null || cat "$tempfile"`). So the working-tree file holds garbage followed by
`U2FsdGVkX1…`. Smudging the blob again reproduces the same bytes, and the diff comes out empty. It does not start
with `U2FsdGVkX1` either, so a prefix check reads it as decrypted.

Four signals did catch it. `git status` listed the file as ` M`, init printed `please check your password`,
re-cleaning the file no longer reproduced the stored blob, and openssl exited 1. To ask which key a blob is
under, decrypt it with the candidate key and assert openssl's exit status, never its output:

```bash
K="$(doppler secrets get TRANSCRYPT_KEY --project tools --config prd --plain)"
git cat-file -p HEAD:<path> | ENC_PASS="$K" openssl enc -d -aes-256-cbc -md MD5 -pass env:ENC_PASS -a >/dev/null 2>&1 && echo "Doppler key: <path>" || echo "NOT the Doppler key: <path>"
unset K
```

Scored on output instead, a key-rotation sweep read the one repo still on the old key as decrypted: 1609 bytes
of output with exit 1. Two sessions wrote that bug independently the same day, the second scoring `[ -n "$out" ]`
on a pipeline ending in `head -c 200` — which discards the status a second time — so treat it as the reflex the
check has to be written against, not as one slip. A wrong key can also pass the padding check by chance, roughly
once in 256 files.
Where the clone is set up, compare the decrypted output with the working copy too, by replacing `>/dev/null`
with `| cmp -s - <path>`. A clean `git status` is another signal. Being set up and holding encrypted files
says nothing about which key the blobs are under. The same sweep first reported four repos as unrotated on that
basis, when all four were done.

### Asking the same question with no key material

Where the clone is configured, the clean filter answers it without a passphrase ever reaching a variable.
Ciphertext is deterministic over `<filename>:<password>` and the content, so re-cleaning the working-tree file
reproduces the stored blob exactly when the two are under the same key:

```bash
CRYPT_DIR="$(git rev-parse --git-common-dir)/crypt"
[ "$("$CRYPT_DIR/transcrypt" clean context=default "$F" < "$F" | git hash-object --stdin)" = "$(git rev-parse "HEAD:${F}")" ] \
  && echo "blob is under this clone's key" || echo "blob is under some other key"
```

Prefer it wherever the clone is set up: `secret-print-guard` refuses `transcrypt --display` and any `git config`
read that would expose `transcrypt.password`, so a check built around the clone's own passphrase has nowhere to
get it, while this one never asks. Its reach stops at the clone, though — it says the blob and the working tree
agree under whatever key is configured here, and nothing about *which* key that is. To name the key, the openssl
form above is the only one that does it, because it supplies the candidate itself.

## A prepped repo on an un-initialised machine commits plaintext

Steps 1 and 2 being independent has a consequence worth stating on its own, because it is the state of **every
fresh clone** until someone unlocks it: `.gitattributes` is committed, so the path matches `filter=crypt`, while
`filter.crypt.clean` is absent and `filter.crypt.required=true` — the thing that would turn a missing filter
into a hard error — is *local* config that is absent with it. Git then passes the content through untouched and
stages plaintext, reporting nothing.

This defeats the obvious pair of pre-commit guards. A structural check ("is the path marked `filter=crypt`?")
passes, because the attribute is committed. A content check guarded on the per-repo transcrypt copy existing
(`[ -x .git/crypt/transcrypt ] || exit 0`) no-ops, because that copy is exactly what a fresh clone lacks. The
two together look like defence in depth and have a shared blind spot. Make the content check unconditional —
if a staged path resolves to `filter=crypt`, assert the staged blob starts with `U2FsdGVkX1`, whether or not
transcrypt is installed in that clone.

## The migration's first symptom is a refused pull, not a decryption problem

Un-ignoring a per-machine config into a versioned-encrypted one is not finished when it is committed. Any
machine that **had a copy of its own** and has not pulled since still holds it, untracked, at exactly the path
the incoming commit adds — so git refuses the merge before any filter behaviour is reached:

```
error: The following untracked working tree files would be overwritten by merge:
        config/publish.env
```

That names a *file collision*, not a filter, so it reads as unrelated to the encryption work — and where it
applies it is guaranteed rather than unlucky: the collision IS the migration. Move the local copy aside, pull,
and only then does the locked-clone case below apply. Once the repo is unlocked, delete the copy that was moved
aside rather than merging it back: the committed one is the source of truth, and keeping a per-machine edit
alive is the drift the migration existed to end.

**Establish which machines actually had one before warning about any of them.** A per-machine config exists only
where the per-machine job ran, so a repo that publishes from a single machine has exactly one copy and nothing
to collide — while the hazard reads as universal and gets asserted about every checkout. In one repo that guess
was made by three separate sessions before the correction was written into project memory, and a fourth session
repeated it into a runbook anyway. The recorded fact outranks the plausible mechanism; go and read it.

## A reader of an encrypted config must not report a key as absent

The same locked-clone state has a mirror-image consequence for whatever *consumes* the file. On a clone nobody
has unlocked, a versioned-encrypted config is ciphertext in the working tree, so a tool that parses it — a
line-wise `KEY=value` read, a `grep`, a `source` — finds no keys at all. The failure is total and looks
ordinary: not a parse error, just a config with nothing in it.

So a message must never assert the key is *missing*. "config/publish.env has no VHOST_SRC line" sends someone
to add a second one, on top of the encrypted line already there. Say what is true — no value was readable —
and name the locked-clone case as a cause:

```python
missing = ("no VHOST_SRC is readable in config/publish.env — a transcrypt-locked checkout reads as "
           "ciphertext, so unlock it first" if has_env else "there is no config/publish.env")
```

The distinction is worth the extra clause anywhere a config moved from gitignored-per-machine to
versioned-encrypted: the file's *absence* stops being the normal failure and its *unreadability* takes over,
while every message written for the old world still says "missing".

## Never initialise transcrypt on a deploy checkout

A server's checkout of a repo containing encrypted files is fine untouched: with no crypt filter the file lands
as inert ciphertext that nothing reads. Do not "fix" that. `transcrypt init` sets `filter.crypt.required=true`,
which turns every future checkout there into a hard failure unless the key is present — and the shared
passphrase decrypts every transcrypted file in every repo, so it must never sit on a public-facing host. The
safe state looks accidental and is correct; leave it.

## Verifying a rekey, where every ordinary signal reads wrong

`transcrypt --rekey` re-encrypts the marked files under new credentials, stages them, and prints `*** COMMIT
THESE CHANGES RIGHT AWAY! ***`. Three things about the state it leaves behind mislead in sequence, measured
2026-09-29 on transcrypt 2.3.3-pre after a shared-passphrase rotation.

**1. `git diff` shows ciphertext on one side and plaintext on the other.** `diff=crypt` installs a textconv and
git runs it on *both* blobs, but only one of them decrypts: the new blob opens under the key now configured,
while the old blob cannot be read at all, so git prints it raw. The diff therefore reads as the whole file
having changed from binary noise into plaintext, which looks like the encryption was torn off. It is an artifact
of the key change and nothing else. It also means **any tool that probes `git diff` emits the file's plaintext**
into wherever that probe's output goes — worth knowing before running a rekey inside a flow that captures diffs.

**2. The summary looks exactly like a phantom modification.** Because the plaintext is byte-identical by design,
`--stat` reports:

```
config/publish.env | Bin 2840 -> 2840 bytes
1 file changed, 0 insertions(+), 0 deletions(-)
```

A rule that reads "changed path, no insertions, no deletions" as a stale stat cache will diagnose this as
nothing to commit. The honest discriminator is the blob, not the diff:

```bash
git rev-parse :<path>        # staged
git rev-parse HEAD:<path>    # committed — differs iff there is real ciphertext to commit
```

**3. Any `git reset HEAD` throws the staging away.** Several flows unstage everything early as a hygiene step,
and that silently undoes what rekey staged — leaving a tree that looks clean while the repo still holds
old-key ciphertext. Recovery is a plain `git add <path>`, because the *key* change persists in `.git/config`
even though the index was reset, so the clean filter re-encrypts under the new credentials. On Windows with
git 2.39, a scratch repo measured the same day did not look clean: `git status` listed each file as ` M` after
the reset, with or without a pause first. A signal that differs by machine is no signal at all, so compare the
blobs as in point 2 rather than reading the status either way.

That recovery is safe rather than lucky, and the reason is worth stating: transcrypt derives each file's salt
by HMAC over `<filename>:<password>` and the content, so the ciphertext is **deterministic**. Re-adding an
unchanged file under an unchanged key reproduces the identical blob — verified, the same short sha before the
reset and after. A rekey is therefore idempotent and re-stageable, and a blob that comes back *different* on a
re-add means one of those three inputs moved.

The assertion that settles all three is the round trip. It proves the staged blob decrypts under the key the
clone now holds, which after a rekey is the key passed to it. On its own it cannot tell a right key from a wrong
one, as "A wrong key passes the round trip" above shows:

```bash
git cat-file -p :<path> | "$(git rev-parse --git-common-dir)/crypt/transcrypt" smudge context=default | diff - <path>
```

Finally, `--rekey` **rewrites `transcrypt.openssl-path`** exactly as `init` does, so any openssl shim has to be
rewired afterwards or every subsequent `git status` resumes printing the deprecated-KDF warning. The value it
writes is the built-in default `openssl` rather than the path configured before, because `save_configuration`
skips its already-configured guard on a rekey and goes on to write the same keys `init` writes. One helper,
`is_salt_prefix_workaround_required`, does reload a configured path, but every call site wraps it in a command
substitution, so that assignment dies with the subshell; `--upgrade` is the only mode that reads the old value
back and restores it.

## The general lesson

A "no secrets found" result is only as good as the thing you searched. When a verification greps for something
and finds nothing, confirm the input was non-empty before believing it — an empty haystack passes every test.
Print a byte count next to the verdict so the two cannot be read apart.

## Splitting content rather than encrypting all of it

When only part of what you are writing is sensitive, prefer two files over encrypting the lot: coordinates
(hostnames, usernames, addresses, what is exposed) into an encrypted memory, and the reusable technique — which
is the part worth having indexed and greppable — into a plaintext learning that names none of them. Verify the
split by grepping the plaintext file for every identifier before committing, not by remembering to be careful.
