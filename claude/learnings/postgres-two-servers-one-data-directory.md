# Two Postgres servers on one data directory

Postgres is built to make this impossible: a server writes `postmaster.pid` into its data directory at
startup, and a second server reading that file refuses to start. Under Docker the refusal does not happen,
because the lock file records a PID and each container's postmaster is PID 1 inside its own namespace.

`CreateLockFile` treats a recorded PID equal to its own as its own stale lock and overwrites it. Both servers
are PID 1, so the second one concludes the file is its own leftover and proceeds. The shared-memory
cross-check that would otherwise catch it compares against a different IPC namespace and also passes. Both
servers then run, each with its own buffer pool, both believing they own the directory.

The usual way in is a compose service rename. Rename a service and the old container keeps running, unmanaged
and unmentioned, holding the volume it was started with — while the new one mounts the same named volume at
the same path. Nothing reports it. Both containers report healthy, `pg_isready` answers on both, and the
application behaves normally because it only ever talks to one of them.

## Which server owns the directory

Read the lock file from inside each container:

```
docker exec <container> head -4 /var/lib/postgresql/data/postmaster.pid
```

Identical bytes from both is the confirmation. Line 3 is the postmaster's start time as a Unix timestamp, and
it names whichever server wrote the file last — normally the one that started most recently. The other server
is running without owning its own lock.

`pg_controldata /var/lib/postgresql/data` inside either container reads the same on-disk file, so it cannot
distinguish them either. It is still worth running for `Data page checksum version`, which decides whether you
have any integrity oracle at all (see below).

## Whether the stale server has actually written anything

This is the question that decides how bad the situation is, and it is answerable without touching either
database. Two instruments, both read-only:

**Client backends.** `docker exec <container> ps -eo pid,args` lists the postmaster's children by process
title. A server with no clients shows only housekeeping — checkpointer, background writer, walwriter,
autovacuum launcher, logical replication launcher. A connected client appears as its own
`postgres: <user> <db> <addr>(<port>) idle` line. No such line means nothing is driving writes.

**Log silence.** With `log_checkpoints` on, which is the default from PG15, a completed checkpoint logs a line.
A *time-triggered* checkpoint is skipped silently when no WAL has been written since the last one — so a
server that has logged nothing for hours has written no WAL for hours. That turns silence into evidence rather
than absence of evidence, which is the step worth getting right.

Put together: a stale server whose last log line is a **completed** checkpoint, with no client backends since,
has a clean buffer pool from that checkpoint onward and nothing to re-dirty it. A checkpoint flushes every
dirty buffer, so there is nothing left in its pool to flush later. Where that checkpoint predates the live
server's startup, the two postmasters overlapped but the writes did not, and the directory has had one writer
throughout.

**Do not query the stale server to find this out.** A plain `SELECT` sets hint bits on the tuples it reads,
dirtying pages with no WAL record when `data_checksums` and `wal_log_hints` are both off — and the background
writer will eventually flush those pages over the live server's newer versions of them. Every check above is
either a file read or a process listing, deliberately.

## Retiring the stale server: SIGKILL, not a graceful stop

The obvious command is the wrong one. `docker compose up -d --remove-orphans` matches the leftover containers
by label and stops them *gracefully*, and the official `postgres` image sets `STOPSIGNAL SIGINT` — a **fast
shutdown**. Confirm it rather than assuming:

```
docker inspect <container> --format '{{.Config.StopSignal}}'
```

A fast shutdown terminates backends and then writes a shutdown checkpoint: it flushes the stale server's
dirty shared buffers into the directory the live server owns, and rewrites `pg_control` from the stale
server's own in-memory copy. That copy holds whatever checkpoint the stale server last took, so the on-disk
control file is rewound to an older redo location and marked `shut down`. The live server overwrites it at its
next checkpoint, but a reboot in between starts recovery from the stale redo pointer — and if the WAL it wants
has been recycled, from nothing at all.

SIGKILL writes nothing. The process dies with its buffers unflushed, the lock file untouched, and the live
server's state intact:

```
docker kill -s KILL <app-container> <stale-db-container>   # app first, so nothing reconnects
docker rm <app-container> <stale-db-container>             # never -v
docker stop <other-orphan> && docker rm <other-orphan>     # bind mounts only: graceful is fine
```

Kill the application container before the database so no client can reconnect in the window. `docker rm`
without `-v` cannot reach a named volume — and a volume still in use by the live container is doubly out of
reach — but pass the paths explicitly and leave `-v` off anyway.

## Afterwards

**Checksums are probably off**, and that bounds what you can claim. `Data page checksum version: 0` from
`pg_controldata` means Postgres cannot detect a corrupted page, so there is no cheap integrity check and no
way to prove bit-level fidelity after the fact.

**A `pg_dump` is the best available read test**, and it is worth taking before anything is killed. It reads
every heap page of every table, so completing with exit 0 and the `-- PostgreSQL database dump complete`
trailer present proves the heap is readable. It proves nothing about silent corruption. Take it even where the
database is small: on a stack where the volume is in no backup — which is the common case for a container
volume, since a file-level backup has no file to read — the dump is the only copy that exists.

**Row counts before and after the kill** are a cheap confirmation that retiring the stale server changed
nothing, as is the live server's next scheduled checkpoint completing normally.

**A low write rate makes "no gap in the data" weak evidence.** Where a table gains single-digit rows per day,
a day with none is indistinguishable from a day whose rows were lost. Say so rather than reporting continuity
as proof.

## Related

- `docker-volume-retirement.md` — retiring a volume nothing references any more, which is the opposite case:
  there the question is whether anything still needs the data, here it is which of two live servers owns it.
- `docker-compose-shared-host-co-tenancy.md` — the service rename that strands these containers usually also
  leaves them answering to generic DNS aliases on a shared bridge, which is its own hazard.
