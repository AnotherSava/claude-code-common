# Retiring an orphaned Docker volume

Deciding whether a leftover named volume can be deleted. The question splits into three, and the first
check most people reach for answers only part of the first.

## Who references it — containers are not the whole answer

```
docker ps -a --filter volume=<name> --format '{{.Names}}'
```

`-a` matters: it includes stopped containers, which is exactly what you want, since a volume held by an
exited container is not orphaned. Empty output is a real signal.

But this filter sees **containers only.** A systemd unit, a cron job, or a backup script reading
`/var/lib/docker/volumes/<name>/_data` directly is completely invisible to it, and an empty result reads
identically in both cases. Pair it with a name grep over the places that would hold such a reference:

```
grep -rIl "<name>" /etc/systemd /etc/cron* /opt /usr/local/bin
```

That catches a mountpoint path too, since the path contains the volume name. Say which trees you searched
when you report the result — it is not the whole filesystem.

## Does it hold anything the live copy does not

Resolve both mountpoints and compare, rather than reasoning about what *should* be in there:

```
old=$(docker volume inspect -f '{{.Mountpoint}}' <old>)
new=$(docker volume inspect -f '{{.Mountpoint}}' <new>)
diff <(cd $old && find . -type f | sort) <(cd $new && find . -type f | sort)   # file sets
diff -rq $old $new                                                             # content
```

`diff -rq` is a content comparison across the whole tree, so **what it does not list is the finding.**
That inverts the usual reading of a diff and is worth stating explicitly to yourself: the interesting
output is the absence of a file class, not the presence of one.

### Caddy certificate storage, specifically

Certificates live at `caddy/certificates/<ca-directory>/<domain>/` as three files per domain:
`<domain>.crt`, `<domain>.key`, `<domain>.json`. If `diff -rq` lists no `.crt` and no `.key`, then no
certificate material exists only in the old copy — which is the entire question, since re-issuing is what
Let's Encrypt rate-limits (five duplicates per week).

Three files differ routinely between a live volume and a dormant copy, and none of them is a reason to
keep it:

- `<domain>.json` — the metadata sidecar. Its `_retryAfter` is a renewal-backoff timestamp that moves on
  its own, so the live side is simply newer. Diff it as parsed JSON before assuming anything material
  changed; in a real case it was this one field and nothing else.
- `caddy/last_clean.json` — storage-cleaning timestamp, data volume.
- `caddy/autosave.json` — the autosaved running config, config volume.

Also watch for a **second** orphan: a Caddy stack has both `<project>_caddy_data` and
`<project>_caddy_config`, and a note that names only the data volume will leave the config one behind.

## What can still destroy it by accident

`docker compose down -v` removes only volumes the compose file **declares**. So once a project's compose
file drops the declaration, `down -v` in that directory can no longer reach the volume — and a comment
warning that it still can is stale from that moment. Check the live file rather than inheriting the
warning. Conversely, `docker volume prune -a` and `system prune -a --volumes` *do* reach any unattached
named volume, declared or not.

Marking the live volumes `external: true` with an explicit `name:` is what makes them safe from their own
project's `down -v`, and it is usually the change that makes an old fallback copy droppable.

## Afterwards, verify identity rather than liveness

On a shared proxy, "the container is up" proves nothing about which certificates it is serving. Run the
end-to-end identity check: a successful TLS handshake on each hostname is what proves the live volume was
the one in use all along. See `docker-compose-shared-host-co-tenancy.md`.

## Safe to delete is not the same as worth deleting

These checks answer whether deletion loses anything. They do not answer whether to do it. An old
certificate volume is an insurance policy against a rate limit, it costs a few hundred KB, and the honest
report separates the verification result from the judgement call rather than presenting one as the other.
