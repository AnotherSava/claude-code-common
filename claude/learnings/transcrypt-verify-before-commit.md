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

## Never initialise transcrypt on a deploy checkout

A server's checkout of a repo containing encrypted files is fine untouched: with no crypt filter the file lands
as inert ciphertext that nothing reads. Do not "fix" that. `transcrypt init` sets `filter.crypt.required=true`,
which turns every future checkout there into a hard failure unless the key is present — and the shared
passphrase decrypts every transcrypted file in every repo, so it must never sit on a public-facing host. The
safe state looks accidental and is correct; leave it.

## The general lesson

A "no secrets found" result is only as good as the thing you searched. When a verification greps for something
and finds nothing, confirm the input was non-empty before believing it — an empty haystack passes every test.
Print a byte count next to the verdict so the two cannot be read apart.

## Splitting content rather than encrypting all of it

When only part of what you are writing is sensitive, prefer two files over encrypting the lot: coordinates
(hostnames, usernames, addresses, what is exposed) into an encrypted memory, and the reusable technique — which
is the part worth having indexed and greppable — into a plaintext learning that names none of them. Verify the
split by grepping the plaintext file for every identifier before committing, not by remembering to be careful.
