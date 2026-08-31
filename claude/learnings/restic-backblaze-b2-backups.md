# restic backups to Backblaze B2

Everything here was measured while setting up one tenant's nightly backup, 2026-08-31, against restic 0.18.1,
and extended the same day while setting up a second one on the same box. The traps are almost all *silent* —
the backup reports success and exits 0 while being wrong — which is why they are worth writing down rather
than rediscovering.

## `forget` groups by host AND paths, so an unstable source path disables retention

The quietest of the lot, because every command involved reports success. From restic's own documentation:

> restic first loads the list of all snapshots and groups them by their host name and paths. The policy is
> then applied to each group of snapshots individually.

So the absolute path you hand `restic backup` is part of the retention key. Stage into a fresh
`mktemp -d` each night — an obvious-looking choice, since the staged copy is disposable — and every
snapshot lands in a **group of one**. `--keep-daily 14` then matches one snapshot per group and keeps all of
them, forever. The backup succeeds, the prune succeeds, the retention summary looks plausible, and storage
grows without bound.

Use a **fixed** staging path (`/var/lib/<project>/backup-stage`), and assert the property rather than the
intent — one line, and it fails the moment someone reaches for a tmpdir:

```bash
restic snapshots --json | python3 -c 'import json,sys; s=json.load(sys.stdin);
print(len({(x["hostname"], tuple(x["paths"])) for x in s}), "group(s) for", len(s), "snapshot(s)")'
# 1 group(s) for 2 snapshot(s)   <- correct
# 2 group(s) for 2 snapshot(s)   <- retention is a no-op
```

The fixed path pays twice: the restore procedure can quote a path that will actually exist, and
parent-snapshot selection works, so nightly runs stay incremental.

## Exit code 3 creates a snapshot and reports partial success

`restic backup` exits **3** when some source files could not be read. A snapshot **is** written — it is
simply incomplete. Treat 0 and 3 as different outcomes explicitly, because the natural `if code != 0:`
lumps 3 in with real failures while the natural `if code == 0` lumps it in with success, and only one of
those is even visible:

```python
code, out, err = run("restic", "backup", ...)
if code == 3:
    incomplete = True          # a partial snapshot is not a backup — record WHY, not just that
elif code != 0:
    raise ...
```

A file vanishing mid-walk is the common cause, and for a certificate store that is the same renewal race
the staging copy exists to shrink.

## Use the S3-compatible API, not restic's native `b2:` backend

restic's own documentation steers away from the backend named after the service:

> Due to issues with error handling in the current B2 library that restic uses, the recommended way to
> utilize Backblaze B2 is by using its S3-compatible API.

Backblaze's own restic guide uses S3 as well. The `b2:` backend is not formally deprecated and does work —
a sibling project has run on it nightly for months — but a fresh setup should start on S3, because migrating
later is strictly more work than starting there.

```
b2:<bucket>:<path>                                  # native, not recommended
s3:s3.<region>.backblazeb2.com/<bucket>/<path>      # S3-compatible
```

The credentials go in the **AWS-named** variables, which looks wrong and is not: restic's S3 backend reads
the standard AWS names whatever endpoint sits behind them.

```
AWS_ACCESS_KEY_ID       = the Backblaze application key ID
AWS_SECRET_ACCESS_KEY   = the Backblaze application key
```

## The lifecycle rule is mandatory on S3, and its absence is invisible

**This is the one that will cost money for months without a single error.** The S3 backend only *hides* the
files it deletes, where the native backend removes them. B2 buckets default to keeping every version. So
`restic forget --prune` reclaims nothing: the bucket grows without bound while every nightly run reports
success, exits 0, and prints a plausible retention summary.

Set the bucket's lifecycle to **"Keep only the last version of the file"** — on the create-bucket form, or
afterwards at B2 Cloud Storage → Buckets → the bucket tile → **Lifecycle Settings**. Four presets are offered;
that is the second. It is safe for a restic repo because restic never rewrites a file in place — the repo is
content-addressed, so "last version" is the only version.

Cleanup is not immediate. Backblaze runs it on roughly a daily schedule, so storage keeps showing old
versions for a while after the rule is set. That lag reads exactly like the rule not working.

Note where this failure lives: **entirely in B2**. A monitoring check that asserts the unit's exit status
will stay green forever, and *restic* cannot see it either — an S3 LIST returns only current versions, so
`restic stats` reports restic's own post-prune view and stays flat however much garbage is accumulating.

**But the host is not blind to it — ask B2 instead of restic.** The same bucket-scoped key restic already
uses can read the bucket's lifecycle rules and list file versions over B2's *native* API (HTTP Basic to
`b2_authorize_account`, then plain JSON — no SigV4 signer needed), which makes this checkable from a nightly
job rather than merely known about. Verified 2026-08-31 with a key holding only
`listBuckets, listAllBucketNames, listFiles, readFiles, shareFiles, writeFiles, deleteFiles`:

```
b2_list_buckets       -> buckets[0].lifecycleRules
b2_list_file_versions -> files[].action == "hide" for each hide marker awaiting collection
```

A correct rule reads exactly:

```json
{"daysFromHidingToDeleting": 1, "daysFromUploadingToHiding": null, "fileNamePrefix": ""}
```

**Assert the shape, not the presence.** Two wrong rules both satisfy "a lifecycle rule exists" and neither
does the job: one whose `fileNamePrefix` scopes it to a different path never touches this repository's
objects, and one with `daysFromUploadingToHiding` set hides *live* backup data on a timer. So require a rule
whose prefix is empty or a prefix of the repository path, with a small integer `daysFromHidingToDeleting` and
a null `daysFromUploadingToHiding`.

Prefer this over a size threshold. Absolute byte floors are the intuitive check and they are useless at
small scale: a few-hundred-KB repository accumulates single-digit KB of unreclaimed garbage per night, so a
"fail above 100 MiB of excess" rule is thousands of nights from firing. Counting hide markers measures the
artefact directly and fires immediately.

## The application key

A **master** application key cannot be used at all:

> You cannot use your master application key with the S3-Compatible API.

It fails as a credential error, so it presents as a wrong password rather than a wrong *kind* of credential.
The master key's ID is really an account ID, which is the giveaway — and a cheap pre-flight that never prints
the value:

```bash
n=$(printf %s "$KEY_ID" | wc -c)     # 25 => regular application key (account id + 13)
                                     # 12 => the master key, will not work with S3
```

Three more things to get right at creation time, each failing late and confusingly:

| Setting | Why |
|---|---|
| **Read and Write** | `forget --prune` deletes. A read-only key fails only at the prune step — months in, after every earlier run passed. |
| **Allow List All Bucket Names** | Without it S3 `ListBuckets` is refused; clients that call it during init fail with a bare 403 naming neither bucket nor capability. |
| **No expiry** | A key with a duration expires silently, long after anyone remembers the timer exists. |

Copy the secret immediately — Backblaze shows it exactly once. The **S3 endpoint is displayed in that same
box**, which is the easiest place to capture the region.

Also: buckets and application keys created before **2020-05-04** are not S3-compatible at all and must be
recreated. Only relevant to old accounts, but it presents as an inexplicable auth failure.

### The master key is useless for S3 and necessary for provisioning

Both halves are true at once, which is why the "cannot be used at all" rule above needs a companion. The
master key cannot authenticate to the **S3** endpoint — but over B2's **native** API it is the only
credential that can create the per-project keys, so it is what makes provisioning scriptable instead of a
console trip per project.

- **Its keyID is the account ID.** There is no separate id to store; `b2_authorize_account` takes
  `Basic base64(<accountId>:<masterKey>)`. That is also the 12-vs-25 character tell in the pre-flight above.
- **`writeKeys` is not grantable through the console's key form.** A console-created "All buckets / Read and
  Write" key does carry `writeBuckets`, so it can create *buckets* — but not `writeKeys`, `deleteKeys` or
  `listKeys`. Minting a bucket-scoped key with `b2_create_key` therefore requires the master key. (Measured:
  two ordinary per-bucket keys on one account both listed `writeBuckets` and neither listed `writeKeys`.)
- **Regenerating it invalidates only the master secret.** Every application key keeps working — verified by
  regenerating and then re-authenticating three existing bucket-scoped keys, while the previous master secret
  went to HTTP 401. So a leaked master key is cheap to rotate, and rotation is the right move rather than a
  reason to avoid holding one.
- **`b2_create_bucket` takes `lifecycleRules` inline**, so the rule that section above calls mandatory can be
  set at creation rather than remembered afterwards.

Give each project its own bucket and its own key scoped to it, with file capabilities only and no
bucket-management rights — then a compromise of one project's box cannot read, reconfigure or delete another
project's history. Keep the master key in the secret manager, not on any box it provisions for.

## The endpoint is region-specific, and the region is a property of the account

`s3.<region>.backblazeb2.com` — e.g. `us-west-001`. A B2 account lives in exactly one region and cannot hold
buckets outside it, so this is not a per-bucket choice and every bucket on one account shares it. A guessed
region produces a repository URL that **authenticates and then finds nothing**, which reads like an empty
repo rather than a wrong address.

## Do not enable bucket encryption, and never Object Lock

- **Encryption is redundant.** restic encrypts contents *and* metadata client-side before upload — AES-256
  with Poly1305 authentication, key derived from `RESTIC_PASSWORD` via scrypt. Filenames, sizes and directory
  structure are all ciphertext. Someone with full account access sees opaque blobs. Keep the passphrase in a
  secret manager rather than on the machine being backed up; that, not the bucket setting, is the encryption
  that protects anything.
- **SSE-B2** (Backblaze-managed keys) is transparent to restic and free, so it is harmless if you want it. It
  helps only against a physically stolen drive and does nothing against anyone holding the credentials.
- **SSE-C** (customer-managed keys) is not usable — restic's S3 backend cannot supply a per-request key.
- **Object Lock must stay off.** It makes objects undeletable for the retention window, and the retention
  policy must delete. Enabling it converts a working backup into one that fails every night from the first
  prune onward.

## Getting the credentials onto the box: render from a workstation, not on it

The systemd unit reads an `EnvironmentFile` holding `RESTIC_REPOSITORY`, `RESTIC_PASSWORD`, the two AWS-named
B2 slots and whatever the dump needs. Since the passphrase lives in a secret manager rather than on the
machine being backed up, that file has to be rendered from it — and the obvious runbook line renders it
**on the box**:

```
for k in ...; do echo "$k=$(doppler secrets get "$k" ... --plain)"; done > /etc/app/backup.env && chmod 600 ...
```

Two defects, and both hide until a rebuild.

**The box may not have the secret-manager CLI at all.** A hardened VPS often has no `doppler` binary, so the
loop cannot run where it is documented to run. Nobody notices because the file was created by hand the first
time and has been correct ever since: the method that worked is not the one written down. It surfaces during
a rebuild, which is the worst moment — the `EnvironmentFile` is missing or empty, so the unit loads, the timer
arms, `systemctl status` reads clean, and every fire dies unauthenticated. Render from a workstation instead
and let the values cross the ssh pipe, where they also stay out of both shells' history:

```
for k in RESTIC_REPOSITORY RESTIC_PASSWORD AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY MONGODB_URI; do
  printf '%s=%s\n' "$k" "$(doppler secrets get "$k" -p <project> -c prd --plain)"
done | ssh root@<host> 'umask 077; mkdir -p /etc/app && cat > /etc/app/backup.env'
```

**`chmod 600` after the redirect is a repair, not a guard.** Root's umask is 022, so the shell creates the
file 0644 and the passphrase sits world-readable until the chmod runs — a window rather than a state, which
is why it reads as correct in review and survives on a box shared with other tenants. Setting `umask 077`
before the write closes it instead.

Worth testing the loop with a stub in place of the secret CLI (`printf 'value-of-%s\n'`) and checking the
resulting mode: it verifies the quoting and the ordering without putting a real passphrase anywhere.

## The ExecStart script's mode is recorded in git, not in your working tree

When the box deploys by cloning the repo, the **git index** is what travels. A script that is `chmod +x`
locally but committed 100644 arrives non-executable and the unit dies `203/EXEC` on every fire —
indistinguishable from an ExecStart pointing at the wrong path, and invisible to any check that asks the
filesystem, because locally the bit really is set. Assert on `git ls-files -s <path>` returning `100755`;
repair with `git update-index --chmod=+x <path>`.

## Verifying a restore, as opposed to declaring one

Two ways a drill can look like it passed without proving anything.

**A dry run reporting zero is indistinguishable from an empty archive.** `mongorestore --dryRun` ends with
`0 document(s) restored successfully`, which is correct for a dry run and identical to what an empty dump
would print. It proves the archive *parses*, nothing more.

Restore into a scratch namespace and count the documents back out:

```bash
mongorestore --uri "$URI" --archive --gzip --nsFrom="app.*" --nsTo="drill.*" < dump.archive.gz
mongosh "$URI" --quiet --eval '
  const d = db.getSiblingDB("drill");
  d.getCollectionNames().sort().forEach(c => print(c + ": " + d[c].countDocuments()));'
# ...then drop the scratch database
```

That also proves the indexes came across, which a document count alone does not — worth checking explicitly
when a unique index is what enforces a domain rule.

**`--dryRun` still needs `--uri` against an authenticated server.** mongorestore asks for `buildInfo` before
it parses anything, so an unauthenticated connection dies at the handshake:

```
error getting server version: error getting buildInfo: (Unauthorized) Command buildInfo requires authentication
```

A runbook that prints a `--dryRun` line without `--uri` — while the swap-in line beneath it has one — makes
the single command meant to *verify* a restore the only one that cannot run. Found by executing the drill
rather than reading it.

## Staggering against a co-tenant

Two restic runs against the same upstream on one small box contend for CPU and bandwidth. If a neighbouring
project already backs up at some hour, offset by enough to clear it (40 minutes was ample for a few-MB
repository) and say why in the timer file, or someone will later "tidy" the two onto the same schedule.
