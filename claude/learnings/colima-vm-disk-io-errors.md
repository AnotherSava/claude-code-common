# Colima: containers stuck "starting" with input/output errors

## The Mac's Docker runtime is Colima, not Docker Desktop

`docker context ls` marks `colima *` as current. There is no Docker Desktop app, so
`osascript -e 'quit app "Docker"'` and `open -a Docker` fail with "Unable to find application
named 'Docker'". Colima runs a headless VM: restarting it opens no window, so it does not need
the ask that relaunching a windowed app does.

## Symptom

A long-running VM, days up, starts failing inside its own disk:

- `docker ps -a` shows a container as `Up N days (health: starting)` while
  `docker exec` answers `container … is not running`.
- `docker logs` fails with `open /var/lib/docker/containers/<id>/<id>-json.log: input/output error`.
- `docker system df` fails with a containerd blob `input/output error`.

The host disk has plenty of room (`df -h` at 85 % on the data volume when it was measured), so
the error belongs to the VM's filesystem rather than to the Mac's. An app on top of the
container sees only that its database is unreachable: a Next.js page that queried it returned
HTTP 500, both with and without the change being tested.

## Fix

```bash
colima restart >/tmp/colima.log 2>&1
docker ps -a --format '{{.Names}}\t{{.Status}}'
```

The restart took a few seconds. Containers with a restart policy came back on their own, the
database reported `healthy` about 20 seconds later, and the named volume's data was intact.
Measured 2026-10-28.

## Diagnose before blaming the change

A 500 that shows up during a UI change can predate it. Stash the change, request the page again
and compare the status (`git stash -q && curl … ; git stash pop -q`), then look at the
container's health before reading any application code.

## The VM's data disk grows on the Mac and never shrinks

Colima keeps Docker's data in one sparse image, `~/.colima/_lima/_disks/colima/datadisk`, with a 20 GiB
apparent size by default. It allocates host blocks as the VM writes and does not hand them back when files
are deleted inside the VM: measured 2026-10-30, `colima ssh -- df -h /var/lib/docker` read 13 GiB used
while `du -h` on the image read 19 GiB. So pruning images inside the VM frees room for containers but
returns nothing to the Mac, and a VM disk at 98% costs the Mac no more than one at 70% once the image has
reached its cap.

## A container reports "disk full" while the Mac has room

Docker under colima writes to that VM disk, which neither `df` on the Mac nor a host disk report sees. On
2026-10-29 a `mongorestore` inside a container refused for want of 500 MB while the Mac had 20 GiB free;
`colima ssh -- df -h /var/lib/docker` read 98%. `docker system df` prices what is reclaimable. Unused pulled
images — any for which `docker ps -a --filter ancestor=<image>` prints nothing — are safe to remove, since
a pull brings them back. An old tag of an image that was rebuilt may free almost nothing, because its layers
are shared with the new one. Anonymous volumes can hold data, so removing them is the user's call.
