# Writing and reading a gzipped tar by hand, as a stream

Tar is the obvious container when one downloadable file has to carry a streamed body plus a set of
whole files, and it needs no dependency: a member is a 512-byte header followed by its bytes, padded to
the next 512-byte boundary. Three things about it are not obvious, and each one produces a file that
looks correct.

## A header states its member's size before the payload

This is the constraint that shapes everything else. The size field is in the header, so a member whose
length is not known until it has been written cannot be one member.

For a streamed body — a database export, a log, anything produced lazily — that leaves three options,
and only the last keeps the streaming:

| Option | Cost |
|---|---|
| Buffer the whole body to learn its size | O(total) memory, which is usually what the streaming existed to avoid |
| Measure in a first pass, emit in a second | Reads the source twice, and the source may move between passes |
| Cut the body into fixed-budget members | O(budget + largest record) memory, and the reader concatenates |

Chunking looks odd in a listing and is the only one that scales:

```
header.json
database/000000.ndjson
database/000001.ndjson
attachments/<sha256>
```

Name the chunks zero-padded and fixed-width so `tar tzf` lists them in the order a reader must
concatenate them. Flush after the record that crosses the budget rather than splitting a record, so a
single oversized record inflates one member instead of corrupting two.

The budget is approached from below if you count UTF-16 code units of the text while the member holds
UTF-8 bytes — fine for a ceiling, wrong if you need the figure to be exact.

## The end-of-archive marker lets a reader stop before gzip's trailer

A tar ends with two 512-byte zero blocks. Inside a gzip, those blocks come **before** gzip's own 8-byte
CRC32-and-length trailer — so a reader that returns the moment it sees the zero block never pulls the
last bytes, and `DecompressionStream` raises `Z_BUF_ERROR` only when it is asked for data it does not
have.

Measured: a gzipped tar with its final 8 bytes removed — exactly the trailer — was read back with no
error at all. Every member was intact, so nothing else could have noticed. A truncated archive read as a
complete one.

The fix is to keep reading to EOF after the marker, instead of returning on it:

```js
if (allZero(block)) {
  await drain();   // read to the end so the decompressor checks its own trailer
  return null;
}
```

What follows the marker is zeros — the second zero block, plus whatever padding the writer added to a
block factor — so `drain` can assert that and refuse anything else, which also catches a second archive
concatenated onto the first.

**A library reader will not do this for you.** Measured on Python 3.14.7 against a `.tar.gz` with exactly
its last 8 bytes removed: `gzip -t` fails, bsdtar's `-tzf` fails, and `tarfile.open(path, "r:gz")` iterating
every member *and reading all of their bytes* raises nothing and hands back complete content. What raises is
draining the decompressor — `gzip.open(path, "rb").read()` gives `EOFError: Compressed file ended before the
end-of-stream marker was reached`. Reading the members is not draining it. So "I used the standard library"
is not an answer to this trap; the question is whether the consumer reaches EOF.

**Draining is necessary and not sufficient — translate the error too.** A drained stream raises, but what it
raises is unreadable: `DecompressionStream` throws a bare `TypeError` whose `.message` is the **empty
string**, so `String(err)` is the single word `TypeError`. The useful fields sit elsewhere — `.code` is
`Z_BUF_ERROR` for a short stream, and `.cause` is an `Error` whose own message reads `unexpected end of
file`. Print both.

**The error cannot tell you where the read failed, so do not branch on it.** Measured across eighteen cut
lengths and four ways of consuming the stream: every one raised the identical `TypeError` with an empty
message and `Z_BUF_ERROR`, cuts stopping two bytes inside a ustar header included. No byte count appears on
the object either; the only number is `cause.errno`, which is zlib's error number. A report that seems to
vary with where the archive was cut is coming from the layer above this error, not from it. Route every read
through one translator rather than only the ones on the payload path, because there is no second code to
distinguish them by. A damaged-bytes stream is said to give `Z_DATA_ERROR`; only truncation was exercised
here.

**Catch both ends.** The rejection fires on the readable and the writable side of the stream, and handling
one leaves the other unhandled, which exits the process.

**The general shape:** when an inner format carries its own terminator and an outer one carries an
integrity check, finishing on the inner terminator skips the outer check. Tar inside gzip is one
instance; a length-prefixed payload inside a checksummed envelope is the same trap.

## Two readers walking one archive need the end to be sticky

A natural split is for one pass to take some members and a second pass to take the rest — documents
then files, say. The first pass cannot know it is finished until it has read the header of a member that
is **not** its own, so that member has to be parked rather than re-read; a tar stream cannot seek back.

The end state has to be sticky for the same reason. Once `next()` has returned null, the source stream
has ended, so a second call finds no bytes and reports a truncated archive — a correct-looking error
about a perfectly good file. One flag fixes it:

```js
if (over) return null;
```

## `--wildcards` is GNU tar's, and bsdtar refuses it

A script that globs members is not portable. Measured on bsdtar 3.5.3 (what macOS ships as `tar`):

```
$ tar xzOf a.tar.gz --wildcards 'database/*'
tar: Option --wildcards is not supported
```

GNU tar needs the flag, because without it the argument is a literal name; bsdtar globs by default and
rejects the flag. So a glob form can be rehearsed on only one of the two platforms — which matters when
the script runs on Linux and is being written on a Mac.

The portable form is to read the names out of the listing and pass them explicitly:

```sh
listing="$(tar tzf "$ARCHIVE")"
# Match the EXACT generated shape, which is also what makes the unquoted expansion safe:
# no name that passes this filter can hold whitespace or start with a dash.
names="$(printf '%s\n' "$listing" | grep -E '^database/[0-9]{6}\.ndjson$' || true)"
# shellcheck disable=SC2086 # deliberately split
tar xzOf "$ARCHIVE" $names | wc -c
```

`tar tzf` is worth running for its own sake before anything else: GNU tar exits non-zero on a malformed
or truncated archive, so the listing doubles as the structural check that `gzip -t` cannot perform —
`gzip -t` validates the gzip and is perfectly happy with a gzip of something that is not a tar.

Two further shell notes, both of which bite on a listing that grows one line per member:

- **`grep -c`, never `grep -q`,** when counting member kinds. `grep -q` exits at its first match, the
  writer upstream takes `SIGPIPE`, and `set -o pipefail` promotes that to the script's exit status. The
  failure appears only once the listing outgrows a pipe buffer, so it works in testing and stops later.
- **Reading one named member needs no `head`.** `tar xzOf <archive> <member>` writes a bounded amount
  and exits 0, which retires the `head -c` / process-substitution dance a line-oriented format needs.

## Header fields worth getting right

- Offsets: name 0, mode 100, uid 108, gid 116, size 124, mtime 136, checksum 148, typeflag 156, ustar
  magic 257, version 263, prefix 345.
- Numeric fields are octal, right-aligned in `width - 1`, NUL-terminated. Throw on a value too large
  rather than truncating — a header claiming a different size than it carries is worse than a refusal.
  An 11-digit size field tops out at 8 GiB; GNU's base-256 extension past that is only worth adding if
  something can actually read it back.
- The checksum is the unsigned sum of all 512 bytes **with the checksum field read as eight spaces**,
  written as six octal digits, a NUL and a space. The sum cannot exceed 512 × 255, so six digits always
  fit. Verify it on read before believing anything else in the block, including the name an error would
  quote.
- `mtime` should be passed in rather than read from the clock. A lazy stream reads the clock whenever
  its first chunk is pulled, which is not the moment the archive is named after.
- Skip the pax and GNU long-name extensions where every name is generated and short. ustar's name field
  is 100 bytes; `attachments/` plus a 64-character digest is 76. Assert the length rather than
  truncating, and reject a non-ASCII name, whose bytes outrun its JS length.

## Verify against the real binary

The reason to use tar at all is that someone recovering a machine has `tar` and may not have your
program. That claim is only worth making if it has been run:

```js
await writeFile(path, gzipSync(archive));
expect((await run('tar', ['tzf', path])).stdout.split('\n').filter(Boolean)).toEqual([...]);
expect((await run('tar', ['xzOf', path, 'header.json'])).stdout).toBe('...');
```

A round-trip through your own reader proves the two halves agree with each other and nothing more.
