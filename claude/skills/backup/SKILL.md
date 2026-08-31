---
name: backup
description: >-
  Give a project on the shared VPS a nightly off-box backup, or work on one it already has —
  provision its Backblaze bucket and bucket-scoped key, write its script and systemd units, render
  its credentials, and prove the restore by running it rather than describing it. Encodes the
  toolkit these co-tenants share: restic to B2, one bucket per project, credentials in
  /etc/<tenant>/backup.env, a staggered timer, and a drill.
  TRIGGER when: a project needs a backup it does not have; an existing backup needs changing,
  diagnosing, or restoring from; a nightly backup unit has failed; a restic repository or a
  Backblaze bucket/key must be created; or someone asks where a project's snapshots live.
  DO NOT TRIGGER when: the task is a one-off dump taken by hand for a migration or a schema change,
  a git or source-code backup, or a project that is not a tenant of this box.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Off-box backups

Every tenant here uses one shape. This skill installs it, and the reason it is a skill rather than a
document is that most of its failure modes are **silent** — the run exits 0 while being wrong — so the
steps that catch them have to be executed, not remembered.

## Context
- Project root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Backup artefacts already here: !`find . -maxdepth 4 \( -name 'backup*.sh' -o -name 'restore*.sh' -o -name '*backup.env*' -o -name '*-backup.*' -o -name '*offsite*' \) -not -path '*/node_modules/*' -not -path '*/.git/*'`
- Publish/deploy coordinates: !`find . -maxdepth 3 -name 'publish.env*' -not -path '*/node_modules/*'`

## The shape

| Piece | Where |
|---|---|
| the job | `<repo>/…/backup.sh` (or a `bin/` command), committed **100755** |
| the restore | `<repo>/…/restore.sh`, restoring to a scratch dir — never over live data |
| the units | `<repo>/…/<tenant>-backup.{service,timer}`, installed to `/etc/systemd/system/` |
| the template | `<repo>/…/backup.env.example` — names and shapes, never values |
| credentials | `/etc/<tenant>/backup.env` on the box, mode 0600, the unit's `EnvironmentFile` |
| the passphrase | that project's Doppler `prd` config, **off** the box it protects |
| the repository | `s3:<endpoint>/<project>-backups/<host>` — endpoint and region from `b2_authorize_account` |
| staging | `/var/lib/<tenant>/backup-stage`, a **fixed** path |

**The per-box inventory is not in this repository, which is public.** Which tenants are backed up, which
are not, the free timer slots and each neighbour's conventions live in the private repo that owns the
shared edge, at `docs/backup-tenants.md` in a sibling `landlord` checkout. Read it before choosing a time
or a convention — the arrangement is deliberate. If no such checkout is present, say so rather than
guessing a slot: colliding with a neighbour's run is the one mistake this arrangement exists to prevent.

`~/.claude/learnings/restic-backblaze-b2-backups.md` has the *why* behind the non-negotiables below. This
file tells you what to do; that one explains what it costs when you don't.

## Process

### 1. Establish what to capture, and how to make it consistent

From **Backup artefacts already here** and **Publish/deploy coordinates**: if artefacts exist, this is a
change to an existing backup — go to the step that matters and skip the rest. Otherwise read the file
named under **Publish/deploy coordinates**, resolving it against **Project root**, for the deploy path,
compose dir and container names. **Never guess the deploy
path**: on this box several projects' repo directory, tenant name, compose project and container name are
four different spellings of one thing, and a unit pointing at the repo name loads fine and dies 203/EXEC
on every fire.

Identify every store holding real data, and never snapshot a live database file:

| Engine | Consistent copy |
|---|---|
| SQLite | `sqlite3 "$DB" ".backup '$STAGE/x.db'"` — the online backup API |
| Postgres | `docker exec -i <project>-db sh -c 'pg_dump -U "$POSTGRES_USER" …'` — credentials from the container's own environment, never a command line. Restore-grade: schema **and** any migration journal |
| Mongo | `docker exec -i <project>-db mongodump --uri "$URI" --archive --gzip` — the tool ships with the image, so its version matches the server |
| files | copy if immutable/content-addressed; otherwise stage them |

Write the dump to a `.partial` path and `mv` it into place only on success — a dump that dies halfway must
not leave a truncated archive for restic to snapshot as though it were good. Address containers by their
project-specific name (`<project>-db`, never `db` or `postgres`): on this box a generic name is a claim on a
shared namespace, which is how a hostname once served a neighbour's app for 41 hours with every check green.

State what you found and what you propose to capture. **Wait for the user** before provisioning anything.

### 2. Provision the bucket and its key

See `references/b2-provisioning.md` — it carries the credential, the exact API script, and the boundary
between what is authorized without asking (creating a bucket, its lifecycle rule, and a scoped key for a
project that has none) and what is not (deleting anything, or touching another project's).

### 3. Generate the passphrase, and store it where the box is not

```bash
python3 -c "import secrets; print(secrets.token_hex(32))" | doppler secrets set RESTIC_PASSWORD -p <project> -c prd --silent
```

Constrain it to hex deliberately. The value round-trips through bash, systemd's `EnvironmentFile` parser
and sometimes compose's dotenv reader, which agree on a simple value and not much beyond it.

Store `RESTIC_REPOSITORY` in the same config. **Without the passphrase the snapshots are unopenable
ciphertext**, so it must not live only on the machine being backed up.

`-c prd`, not the `dev` that `/doppler` defaults to — deliberately, and every tenant here already does it.
These credentials are read by a unit running on the production box; there is no development backup. If a
value must also exist in `dev`, put the real one in `prd` and a `${prd.NAME}` reference in `dev`, so there
is one origin rather than two copies free to drift.

### 4. Write the job, the units and the template

Model them on the closest neighbour (the inventory above says which). Non-negotiables, each of which
fails silently if skipped:

- **A fixed staging path.** restic records absolute source paths and `forget` groups snapshots by host
  **and** paths, so a per-run tmpdir puts every snapshot in its own group and turns retention into a
  no-op — every snapshot kept forever, prune reclaiming nothing, every run reporting success.
- **`export RESTIC_CACHE_DIR=/var/cache/restic`** — a oneshot has no `$HOME`; restic otherwise warns and
  runs cacheless.
- **Tag and a pinned `--host` on both `backup` and `forget`**, so retention addresses one group and the
  box's real hostname is irrelevant.
- **Handle exit code 3.** `restic backup` exits 3 when some sources could not be read — it *writes a
  snapshot* and reports partial success. Record it as incomplete with its reason; `if code != 0` alone
  buries it and `if code == 0` alone accepts it.
- **`TimeoutStartSec=` on the unit.** systemd disables the start timeout by default for `Type=oneshot`, so
  a restic hung on a half-open socket hangs forever holding the repository lock, and the next two nights
  fail on the lock rather than the cause.
- **`ExecStart` under the deploy path**, and the script committed 100755. The git index is what reaches
  the box; a file executable only in your working tree dies 203/EXEC there.
- **An explicit `OnCalendar=*-*-* HH:MM:00` in a free slot, `Persistent=true`, no `RandomizedDelaySec`.**
  Jitter re-collides the runs the stagger exists to separate.
- **Backup first, verify second.** Verify-then-backup means a persistently broken tree produces no backup
  at all, which is backwards: record the defect and keep the snapshot.
- **Do not put these credentials in the publish-time required-secrets list.** A durability credential that
  can block the serving path means an expired key refuses an urgent config change at 02:00.

Write `backup.env.example` with names, shapes and the render loop from step 5 — never a value.

### 5. Render the credentials onto the box

`doppler` is **not** installed on the box, and deliberately: an account credential with far more reach than
the four values would then sit on the machine those values protect. So the loop runs from a workstation
and the values travel over the ssh pipe — no command line, no shell history, and `umask 077` makes the
file 0600 at creation rather than after a window where it was not.

```bash
for k in RESTIC_REPOSITORY RESTIC_PASSWORD AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY; do
  printf '%s=%s\n' "$k" "$(doppler secrets get "$k" -p <project> -c prd --plain)"
done | ssh root@<host> 'umask 077; mkdir -p /etc/<tenant> && cat > /etc/<tenant>/backup.env'
```

The pipe is the mechanism, not a style choice — do not "simplify" it into separate commands.

**You must see** `ls -l` report `-rw------- 1 root root` and the expected key names. Confirm the values by
length, never by printing them.

### 6. Initialise and run once

`restic init` from the box with the env sourced. Then install the units, `daemon-reload`,
`enable --now` the **timer** — and start the **service** once by hand, because arming a timer does not run
it. Check `systemctl show <unit> -p Result -p ExecMainStatus` and the journal, not just the exit code.

### 7. Prove the restore

The step most likely to be deferred, and the one that decides whether any of this was worth doing.
`restic restore` only reads, so it is safe against a healthy box.

Restore the newest snapshot to a scratch directory and **count what came back**, then drop the scratch.
A dry run reporting zero is indistinguishable from an empty archive; a document saying it works is not
evidence. Where the box is still serving, compare a restored artefact against the live one — a matching
SHA-256 proves the copy is identical to production, not merely readable.

Then write the restore procedure down with a **You must see** line per step and a table of what has
**never been executed**, transcribing real output rather than predicting it.

### 8. Record it

Update the project's deploy doc, and say in one line where the snapshots live and how to get them back.
If the project has a self-check, add an assertion on the backup's *freshness and content* — not on the
unit's exit status, which stays green while the repository rots.

## Out of scope

- Do NOT delete a bucket, a key, or a snapshot, or run `forget`/`prune` by hand — see the boundary in
  `references/b2-provisioning.md`
- Do NOT touch another project's bucket, key, lifecycle rule or units; route the finding to that project
- Do NOT put `B2_MASTER_KEY` on any box
- Do NOT restore over live data as part of a drill
- Do NOT commit a credential value, encrypted or otherwise
