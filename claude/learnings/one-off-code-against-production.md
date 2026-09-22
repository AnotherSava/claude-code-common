# Running a deployed app's own code against production, once

A stored result needs recomputing with code that has improved since it was written — a re-extraction, a
re-derivation, one row backfilled. The function that does it already exists and is already deployed. What is
missing is somewhere to *call* it from, and the two obvious places fail for different reasons.

## The runtime image is not a development environment

A production image is built to serve, so its dependency tree is whatever the server bundle traces and nothing
more. Next's standalone output is the worked example: `/app/src` is present and looks promising, while
`node_modules` holds a fraction of what `package.json` lists — no `tsx`, and no package the bundler inlined
into a chunk. So `docker exec <app> npx tsx once.ts` fails on an import rather than on the logic.

Check before planning around it:

```bash
docker exec <app> ls -d node_modules/tsx node_modules/<a-bundled-dep>
```

## Run it beside the stack, not from your workstation

A hardened compose stack publishes no host ports — the database and any sidecar are reachable only from the
stack's own network. Reaching them from a workstation means an SSH forward per container IP, and the database
credential travels to the workstation with it.

Running on the host leaves the credential where it already is. A throwaway container joins the stack's
network, mounts the repo, installs the real dependency tree and calls the real function:

```bash
docker run --rm --network <project>_default \
  -v /opt/<app>/web/.env:/env:ro \
  -v /opt/<app>/web:/src:ro \
  -v /tmp/once.ts:/once.ts:ro \
  node:24-slim bash -c '
    export DATABASE_URI="$(sed -n "s/^DATABASE_URI=//p" /env | sed "s/^\"//; s/\"\$//")"
    cp -a /src /work && cp /once.ts /work/ && cd /work
    npm ci --no-audit --no-fund > /tmp/npm.log 2>&1 || { tail -40 /tmp/npm.log; exit 1; }
    npx tsx once.ts "$@"
  ' --
```

The trailing `--` is what makes appending arguments work: `bash -c <script> a b` assigns `a` to `$0`, so
without a placeholder the first argument vanishes from `"$@"`.

Copying to `/work` keeps `npm ci` out of the host's checkout, which the next `git pull` or image build would
otherwise have to step around. Service names on that network — `<app>-db`, `<app>-extract` — resolve, so the
rendered `.env` needs no rewriting.

The script imports the exported function and prints the row before and after. Restating what that function
does, rather than calling it, produces a confident result computed by code nobody reviewed.

## Parse the env file; do not use `--env-file` and do not source it

Both shortcuts are wrong in opposite directions, and a rendered secret makes each one silent:

- `docker run --env-file` takes the rest of the line verbatim, quotes included. A secret manager writes
  `KEY="value"`, so the container receives the quotes too and every consumer fails on a value that looks
  correct in every log. Compose's `env_file:` *does* strip them, which is why the stack works and the one-off
  does not.
- `set -a; . /env` strips the quotes and then expands what is inside: a value holding a `$` or a backtick
  arrives mangled, or runs something.

Parsing per key with `sed` takes the line literally and strips only the surrounding quotes. Export the two or
three keys the function actually reads, and echo none of them — the file is mounted so that its values never
have to pass through a command line or a transcript.

## Clean up the host

Delete the scripts and remove the base image the run pulled. On a shared box that image is several hundred
megabytes charged to every co-tenant's disk, and the scripts carry whatever the one-off was about.
