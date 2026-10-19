# Retiring a Docker network a running container still names

Taking a container off a network live and then deleting the network looks finished: the container keeps
serving, `docker network ls` no longer lists it, every probe is green. It is not finished until the
container has been **recreated** from a definition that no longer names the network, and nothing
reports the gap until the container next starts.

## What breaks, and when

`docker network disconnect <net> <ctr>` removes the endpoint, which is what lets `docker network rm`
succeed. It does not rewrite `HostConfig.NetworkMode`, which compose sets to the container's **primary**
network when it creates the container — the one it starts with, before attaching the rest. Inspect it:

```
docker inspect <ctr> --format '{{.HostConfig.NetworkMode}}'
```

While the container runs, nothing reads that field. The next `docker start` does — a host reboot under a
`restart: unless-stopped` policy, a daemon restart, a manual stop/start — and it fails outright:

```
failed to set up container networking: could not find a network matching network mode <net>: network <net> not found
```

The container exits `128` and stays down. Its other networks being present does not help; the start is
refused before any of them is attached.

Measured on a shared-proxy host: the proxy was disconnected from a retired bridge and the bridge deleted,
with the compose file's matching edit committed but never deployed. It served for nine days, then a
provider maintenance reboot left every site behind it unreachable while every app container came back
healthy.

## Retiring one safely

1. Remove the network from the compose file and **deploy that file**.
2. Recreate the container from it: `docker compose up -d --no-deps --no-build <service>`. This is the step
   that actually drops the reference; it costs one container restart.
3. Confirm `NetworkMode` no longer names it, then `docker network rm`.

Doing the live disconnect first to avoid the restart only defers that restart to a moment nobody chose.

## Finding the latent case

Before deleting any network, and after the fact on a box where one was deleted:

```
for c in $(docker ps -aq); do docker inspect "$c" --format '{{.Name}} {{.HostConfig.NetworkMode}}'; done
docker network ls --format '{{.Name}}'
```

Any `NetworkMode` naming something absent from the second list is a container that will not survive its
next start. A health check or uptime probe cannot see it, because the container is up.
