# Sizing a large artifact for git (and why transcrypt makes it worse)

## transcrypt inflates by ~37%, which can cross GitHub's push limit

transcrypt stores ciphertext **base64-encoded** — which is why its `.gitattributes` guidance says not to mark
encrypted paths `-text`: the stored form is text. So the blob git receives is meaningfully larger than the file
on disk. Measured by running the same transformation transcrypt's clean filter uses:

```bash
openssl enc -e -a -aes-256-cbc -pbkdf2 -k "<passphrase>" -in big.7z -out big.b64
```

| | bytes | |
|---|---:|---|
| file on disk | 90,044,641 | 85.9 MiB |
| stored blob | 123,811,426 | 118.1 MiB |

That is +37.5%. GitHub rejects a push containing a blob over **100 MiB**, and the limit applies to the file's
own size, not to what it compresses to. So **a file above roughly 76 MiB becomes unpushable once transcrypted**,
while the identical file commits fine in the clear. Nothing warns earlier: `transcrypt` accepts the path,
`git add` and `git commit` both succeed, and the rejection arrives at push time with the commit already made.

Check the encrypted size *before* designating a large file `filter=crypt`, not after.

## A solid archive is the wrong shape for git at any size

Encryption aside, a compressed archive is a single opaque blob. Git cannot delta two versions of one — and a
7z/zip is already incompressible, so zlib gains nothing either. Every re-snapshot therefore writes the **entire**
artifact into history again, permanently, however little of its content changed.

The same data stored as its constituent text files behaves completely differently. Measured on a 403 MB corpus
of append-only JSONL (2304 files):

| approach | first snapshot | second snapshot, 18 days later |
|---|---:|---:|
| one solid `.7z` per snapshot | 86 MB | +86 MB (whole artifact again) |
| the files themselves, packed by git | 139 MB | +98 MB |

Git's 139 MB loses to 7z's 86 MB on the first pass — LZMA2 in solid mode beats zlib per-blob, and always will.
It wins on every pass after that, because unchanged files re-resolve to the same blob hash and cost nothing, so
its growth tracks *new information* rather than total size.

## But "git handles it better" is not the same as "git should hold it"

The second column above is the number that decides it. ~98 MB of genuinely new data per 18 days is ~165 MB/month,
and **git history cannot be pruned** — that is the property the whole tool is built on. A corpus that grows
without bound is therefore the wrong tenant for a git repo regardless of how efficiently git stores each
increment; the repo just reaches an unusable size more slowly.

The shape that works is to split by *what the data is*:

- **Code, docs, config** → git. Small, diffable, benefits from history.
- **The growing corpus** → a content-addressed store built for it: restic, or object storage. Deduplicated,
  encrypted, incremental, and — the property git lacks — **prunable**.
- **Anything derived** (a SQLite index, embeddings) → gitignored, rebuilt on each machine from the corpus.

Git LFS is the only way to keep a large artifact under `git`'s command surface, but it moves the bytes to a
quota'd store rather than removing the problem — check the account's current LFS storage and bandwidth
allowances before assuming it fits, since a clone on each machine draws on the bandwidth quota.

## The general lesson

"Can I commit this?" has three separate answers that are easy to conflate: whether the push will be *accepted*
(a hard per-blob limit, which encryption can push you over), whether git will store it *efficiently* (delta-ability,
which a solid archive forfeits), and whether it *belongs* in permanent history at all (prunability, which no
amount of efficiency fixes). Answer them in that order — the third one most often overrides the first two.
