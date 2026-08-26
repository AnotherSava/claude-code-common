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

Then assert the negative on the *stored* form, not the working-tree form:

```bash
OUT=$("$CRYPT_DIR/transcrypt" clean context=default "$F" < "$F")
printf '%s' "$OUT" | grep -qiE "<secret>|<hostname>|<username>" && echo LEAK || echo clean
```

## The general lesson

A "no secrets found" result is only as good as the thing you searched. When a verification greps for something
and finds nothing, confirm the input was non-empty before believing it — an empty haystack passes every test.
Print a byte count next to the verdict so the two cannot be read apart.

## Splitting content rather than encrypting all of it

When only part of what you are writing is sensitive, prefer two files over encrypting the lot: coordinates
(hostnames, usernames, addresses, what is exposed) into an encrypted memory, and the reusable technique — which
is the part worth having indexed and greppable — into a plaintext learning that names none of them. Verify the
split by grepping the plaintext file for every identifier before committing, not by remembering to be careful.
