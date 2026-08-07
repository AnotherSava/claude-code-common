# Encrypting secrets at rest in a SQLite app (and the residue trap)

How to stop a credential stored in an app's own SQLite database from being readable in backups and snapshots. Verified 2026-08-05 on Node 24 + better-sqlite3 (Prisma 7 adapter). Companion to `prisma7-generic-full-db-backup-sqlite.md`, `node-sqlite-inspect.md`.

## The trap: rewriting the row does NOT remove the plaintext

This is the part that bites. You encrypt the column, rewrite the row, confirm the stored value now reads `enc:v1:…` — and the old plaintext is **still in the file**, and still gets copied into every backup.

SQLite does not zero the bytes of an overwritten or deleted cell. The old content stays in free space inside already-allocated pages until something reuses them, and `db.backup()` copies the **page image**, so snapshots inherit it verbatim.

Reproduced exactly:

```bash
# no LIVE row contains it …
node -e "…SELECT value FROM Setting…" | grep -c 'my-secret-token'   # 0
# … but the file does, and so does a fresh snapshot
grep -c -a 'my-secret-token' prisma/dev.db                          # 2
grep -c -a 'my-secret-token' prisma/backups/latest.db               # 2
```

`PRAGMA freelist_count` was **0** the whole time — the residue was inside allocated pages, not on the freelist, so a freelist check does not detect this.

**Fix:** `VACUUM` after the migration that encrypts the values. It rebuilds the file without the stale content. Run it once, on the same code path that performs the upgrade:

```ts
await setSetting(key, encrypted);
await prisma.$executeRawUnsafe("VACUUM");   // purge the plaintext left in free space
```

Add `PRAGMA wal_checkpoint(TRUNCATE)` too if you're cleaning an existing file by hand — the WAL is a separate file and can hold the old value as well.

**Test the FILE, not the rows.** A row-level assertion passes while the file still leaks, so assert on the bytes:

```ts
await setSetting("cfg", { token: "residue-token-xyz" });          // legacy plaintext row
expect(readFileSync(dbPath).includes("residue-token-xyz")).toBe(true);   // it's really there
await getConfig();                                                // upgrade + VACUUM
expect(readFileSync(dbPath).includes("residue-token-xyz")).toBe(false);
```

Once every write is ciphertext, later residue is ciphertext too — inert — so a single VACUUM at upgrade time is enough. `PRAGMA secure_delete=ON` is unnecessary for that reason.

## Deriving the key: HKDF, not scrypt

If the app already requires a high-entropy secret (a session-signing key), derive the data key from it instead of introducing a second secret to store and lose.

Use **HKDF**, not scrypt/argon2. Those are deliberately slow because they defend *low-entropy passwords*; the input here is already 256 bits of random, so a slow KDF buys nothing and taxes every request that reads the config.

```ts
import { createCipheriv, createDecipheriv, hkdfSync, randomBytes } from "node:crypto";

const key = Buffer.from(hkdfSync("sha256", process.env.SESSION_SECRET!, "app/secrets", "field-tokens", 32));
```

Salt and info are fixed labels, not secrets — they domain-separate this key from the signing use of the same input.

## Envelope + fail-soft

Store `enc:v1:<base64(iv|tag|ciphertext)>` with AES-256-GCM and a random 12-byte IV per value. The version prefix is what lets a legacy plaintext row be recognised and upgraded rather than mis-decrypted.

```ts
const iv = randomBytes(12);
const c = createCipheriv("aes-256-gcm", key(), iv);
const body = Buffer.concat([c.update(plain, "utf8"), c.final()]);
return "enc:v1:" + Buffer.concat([iv, c.getAuthTag(), body]).toString("base64");
```

**Decrypt must not throw.** Config like this is read during ordinary page renders, so a rotated key or a hand-edited row would otherwise 500 the whole site. Return `""` and let the caller degrade to "not configured":

- unprefixed value → return as-is (legacy plaintext, upgraded on next write)
- bad tag / bad base64 / wrong key → `""` + a warning log

That failure mode is only acceptable because **what's encrypted is re-enterable**. Keep it to credentials the user can paste again; never wrap irreplaceable data (history, user content) in a key that can be lost — that trades a small exposure for total data loss.

## Choosing field-level over whole-file encryption

Encrypting *the backup file* is the obvious instinct and is usually the worse trade:

| | field-level | whole-file backup |
|---|---|---|
| covers the live DB | yes | no |
| cost of a lost/rotated key | re-paste 2 credentials | the entire backup |
| restore tooling needed | none | a decrypt CLI, or the snapshot is unusable |
| tying it to a login password | n/a | rotating the password orphans old snapshots |

## Testing gotcha: `process.env.X = undefined`

Node coerces `process.env` assignments to strings, so this sets the **string `"undefined"`**, not an unset variable — a seed-from-env test then reads `"undefined"` as a real value:

```ts
Object.assign(process.env, { PLEX_URL: undefined });  // process.env.PLEX_URL === "undefined"
delete process.env.PLEX_URL;                          // the actual way to unset it
```
