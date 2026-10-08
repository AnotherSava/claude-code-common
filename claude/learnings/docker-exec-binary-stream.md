# Streaming a binary payload out of a container with docker exec

A host-side job that needs bytes from inside a container — a database export, a generated artifact, anything the
app serves rather than writes to a shared mount — reaches them by exec-ing in and letting the program write to
stdout. Three separate mechanisms along that path deliver corrupt or truncated bytes **and exit 0**, so a caller
running `set -euo pipefail` sees a success and whatever consumes the file later is the first thing to notice.

The figures below come from pulling a 1.79 MB gzip out of a Node app.

## Never pass `-t`

A pseudo-TTY rewrites LF to CRLF and merges stderr into stdout. The same artifact came back 1,794,331 bytes
instead of 1,787,859 and `gzip -t` refused it, and a 500 response's JSON body arrived on stdout, inside the
file. Exit status was 0 in both cases.

Pass `-i` alone. Reading a program's stdout does not require it, but a POST that reads stdin does, so one shape
covers both directions.

## Read the body as bytes, not text

Calling `await response.text()` UTF-8-decodes whatever arrived. On a gzip that yields replacement characters,
and `gzip -t` then refuses the file as "not in gzip format".

How much it grows is a property of the payload rather than of the bug, so the size is no way to detect it: 1.79
MB of this archive came back as 3,261,480 bytes, while a gzip of 64 MiB of zeros deflates to nearly all valid
ASCII and grew 1.0016x, with 52 replacement characters. The corruption is total in both. Where a body genuinely
has to be held in memory, `arrayBuffer()` returns it byte-identical.

## Let the process exit on its own

Node's stdout to a pipe is asynchronous, so `process.exit()` after a large write discards everything still
buffered: a 1,787,859-byte `process.stdout.write` delivered 65,536 bytes and exited 0. Set `process.exitCode`
and return instead, and Node flushes before it exits.

Three things narrow when this bites. The boundary is strictly above 65,536 — at exactly that size nothing is
lost, and 65,537 is the first that pins delivery to 65,536. The loss is independent of the status, so a
non-zero exit is no protection: `process.exit(7)` lost the data and `process.exitCode = 7` kept it, both
exiting 7. And redirected to a regular file rather than a pipe, nothing is lost at all, which is why a program
that works when you test it into a file truncates in the pipeline it ships in. Do not re-derive the number
from `getconf PIPE_BUF`, which reports 512 — that is the atomic-write guarantee, not the capacity.

The shape that survives all three:

```bash
docker exec -i "$CONTAINER" node -e '
const run = async () => {
  const { Readable } = await import("node:stream");
  const { pipeline } = await import("node:stream/promises");
  const response = await fetch("http://127.0.0.1:3000/path");
  if (!response.ok) { process.stderr.write(await response.text() + "\n"); process.exitCode = 1; return; }
  await pipeline(Readable.fromWeb(response.body), process.stdout);
};
run().catch((error) => { process.stderr.write(String(error) + (error && error.cause ? " (" + String(error.cause) + ")" : "") + "\n"); process.exitCode = 1; });
' > "$FILE.partial"
```

Use `await import` rather than `require`, so the program does not depend on whether `node -e` is treated as
CommonJS or ESM in that image. The `error.cause` clause carries the only useful half of a mid-stream death: the
body gives up as `TypeError: terminated`, and the reason — `SocketError: other side closed` — is in the cause.

## Verify the bytes before publishing the name

Write to a `.partial` path and rename only after a check that reads the content. A rename marks a file whole
given that the writer said so, and each mechanism above is a writer saying so wrongly:

```bash
[ -s "$FILE.partial" ] || exit 1
gzip -t "$FILE.partial" || exit 1
mv "$FILE.partial" "$FILE"
```

The only step in the chain that reads the bytes is `gzip -t`, and its **exit status is the whole of the
signal**. Measured against damaged copies — truncation at several points, a flipped payload byte at six
offsets, a flipped byte in the trailer's CRC32 — every one exits 1. Do not branch on the message, which does
not say which damage it was: five of six payload-flip offsets printed "invalid compressed data--crc error",
while a flip 997 bytes from the end printed "unexpected end of file", the same text a truncation gives. Each
failure prints two stderr lines, the second always `gzip: <file>: uncompress failed`.

It costs 0.006 s on a 1.79 MB file. The `.partial` suffix is fine for `-t` and `-cd`; `gzip -d` is the one that
refuses it, with "unknown suffix -- ignored".

What it cannot see is a payload that is intact gzip and incomplete *content*. A database export whose source
changed mid-read is a valid archive carrying fewer records than its own header promises — on a standalone
MongoDB, deleting 100 of 500 rows with the export cursor open produced exactly that, and gunzipped without
complaint. Catching it needs a count inside the format, compared after the last record is written.

## Reading one line out of a gzip under pipefail

Assigning `header="$(gzip -cd "$F" | head -1)"` kills the script with 141 under `set -euo pipefail`: `head`
closes the pipe, gzip takes SIGPIPE, and pipefail promotes that to the pipeline's status. Put the pipeline
inside a process substitution, where its status is not the shell's:

```bash
read -r header < <(gzip -cd "$F" | head -c 4096) || true
```

The same trap catches a membership test written as `restic ls "$SNAPSHOT" | grep -q "$PATH"`, which is a false
negative on a listing long enough to fill a pipe buffer — measured on one over 200 KB, answering
`PIPESTATUS=141 0` and "not found" on a snapshot that did contain the path, while a listing of a few hundred
bytes answered correctly. Capture the listing first and match with `[[ "$listing" == *"$needle"* ]]`.
