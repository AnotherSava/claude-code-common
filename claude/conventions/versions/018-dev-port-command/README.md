---
title: A dev script resolves its port through the dev-port command, not a copied shim
---

## What changed

Version 015 had each repo copy a `scripts/dev.mjs` shim that loads the ports skill's resolver with two
names spelled out: the registry use case and the repo's GitHub name. Every copy differs only in those two
names, both of which are derivable — the use case and the owner are what `ports.py dev-use-case` prints
without and with `--owner`, which is what `deploy-dev-server.sh` already asks. A fix to the
shim's own error handling reached no copy.

The ports skill now ships a `dev-port` command in its `bin/`, which the dotfiles install puts on `PATH` on
both machines. A dev script reads `"dev": "dev-port next dev"` (or `"doppler run -- dev-port next dev"`),
and the command finds the project root from wherever npm runs it, derives both names and starts the server
with `PORT` set. A repo carries no file for it.

## Migrating an existing repo

1. **Check the command is reachable on this machine.** `command -v dev-port` must print a path. If it
   prints nothing, the machine's install predates this version: pull the dotfiles repo, run the PATH line
   from its README's install block for this OS, and open a new terminal.
2. **Confirm the shim is a plain copy.** Read `scripts/dev.mjs`. It qualifies when it does nothing but load
   `dev-port.mjs` and call `run` with its `USE_CASE` and `OWNER` constants, as version 015's template does.
   A file with logic of its own — tauri-dashboard's writes a Tauri config override — is not a shim: leave
   it and stop here.
3. **Confirm the derived names match.** On every clone, `USE_CASE` must equal what `python3
   ~/.claude/skills/ports/scripts/ports.py dev-use-case --from <the dir the dev script runs in>` prints,
   and `OWNER` what the same command prints with `--owner` added — that is what `dev-port` asks. Run it on
   the other machine over SSH, with the login in the `machines-private` memory. Where either differs, `dev-port` would ask for a different claim than the
   one the registry holds: stop and show the user both values.
4. **Point the dev script at the command.** In every `package.json` whose script runs
   `node <path>/scripts/dev.mjs`, replace `node <path>/scripts/dev.mjs` with `dev-port`, keeping the rest
   of the line: `doppler run -- node ../scripts/dev.mjs next dev` becomes `doppler run -- dev-port next dev`.
5. **Delete `scripts/dev.mjs`** once a grep finds nothing else naming it. It holds nothing but the two
   names step 3 confirmed are derivable, so nothing is lost.
6. **Check it runs.** Run the dev script by hand from its directory, for example `npm run dev`, and read
   the `dev-port: <use case> -> <port>` line it prints against `ports.py list`; stop the server after.
   Then run `deploy` the way the repo deploys. Both must arrive at the same port.
7. **Hand the other clone its half** if it is on another machine: its session needs step 1 there before
   its next `npm run dev`, so send it one message, as the `peer` skill describes.

## When it does not apply

- **No `scripts/dev.mjs`** in the repo's tracked files: it never copied the shim.
- **A `scripts/dev.mjs` with logic of its own**, settled by reading it in step 2.

## Continuing rule

None — this is a one-time migration. The `ports-from-registry` rule from version 015 already reports a
repo whose dev script stops resolving its port, and it recognises `dev-port` as a resolver.
