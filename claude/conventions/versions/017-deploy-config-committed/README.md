---
title: A project's deploy settings are one committed file, and no wrapper stands in front of them
rules: deploy-config-committed
optional: forks
---

## What changed

Each machine kept its own copy of a project's deploy settings, because `config/deploy.env` was in the
global excludes. A decision the project made — run a sync on `deploy --db`, render the config from
Doppler, which dev command to run — was typed in again on every clone, and the copies drifted: one
Tauri project rendered its secrets from Doppler on Windows and shipped a plaintext config on macOS.
Where the settings file had no key for something, a hand-written `scripts/deploy.sh` took it on, and
three of those implemented the same `--db` feature three different ways. Rerunning the deploy skill
regenerated each wrapper and dropped the feature without a word.

Now:

- **`config/deploy.env` is committed** and names a `DEPLOY_TYPE` for every target: `dev-server`,
  `tauri`, `intellij-plugin` or `dotnet`. The global excludes no longer hide it.
- **`config/deploy.local.env` holds only what differs between machines**, such as an IDE's plugin
  directory, and overrides the committed file key by key. It stays in the global excludes. Most
  projects have none.
- **The `deploy` shell function runs the deploy skill's `scripts/run.sh`**, which reads `DEPLOY_TYPE`
  and calls that target. There is no per-repo wrapper.
- **What the wrappers did by hand is now a setting of the shared scripts:**
  - `DEV_DB_SYNC_CMD` — the command `deploy --db` runs between stopping a dev server and starting it
    again, replacing the local data with production's.
  - `DOPPLER_PROJECT` and `DOPPLER_CONFIG` — where a Tauri app's `config/local.template.json` is
    rendered from.
  - `SECRET_FILE` and `SECRET_FIELDS` — Doppler secrets written into fields of an app's own settings
    file, leaving the rest of it as the app saved it.
- **`INSTALL_DIR` has a per-OS default**: `/Applications` on macOS, `C:/Programs/<binary name>` on
  Windows. The key is needed only where a project installs somewhere else.

The full key list for each target sits in the header of its script under the deploy skill's
`scripts/`, and the shared reader is `claude/skills/shared/deploy-config.sh`.

## Migrating an existing repo

The two clones of a repo hold different settings, so read both before writing one. Do this from the
session that owns the repo, on one machine; the other clone takes the result through `/pull`.

1. **Make sure this machine has the dotfiles change.** `~/.claude/skills/deploy/scripts/run.sh` must
   exist. If it does not, pull the dotfiles repo first.
2. **Read both clones' settings.** On this machine: `config/deploy.env`, `config/deploy.local.env` if
   there is one, and `scripts/deploy.sh`. On the other machine read the same three files over SSH, with
   the login in the `machines-private` memory. A file missing on one side is an answer; an SSH failure
   is not, so stop and say so.
3. **Write the committed `config/deploy.env`.**
   - Add `DEPLOY_TYPE`, taken from the target script the wrapper calls: `deploy-dev-server.sh` is
     `dev-server`, `deploy-tauri.sh` is `tauri`, `deploy-intellij-plugin.sh` is `intellij-plugin`,
     `deploy.sh` is `dotnet`.
   - Delete `DEV_PORT`. The ports registry owns the port and nothing reads the line.
   - Delete `INSTALL_DIR` where it equals the per-OS default on each machine, comparing case-blind on
     Windows. Where it differs and the path is genuinely per machine, as an IntelliJ plugins directory
     is, move it and any `IDE_*` key into `config/deploy.local.env` on each machine.
   - Keep every other key both clones agree on. Where a key exists on one clone only, or the clones
     disagree, show the user both values and ask which one the project means, unless the value is a
     per-machine path, which goes into that machine's local file.
4. **Move what each wrapper does beyond calling its target.** Read every line of both wrappers.
   - A `--db` flag that runs a sync or seed script: set
     `DEV_DB_SYNC_CMD=bash scripts/<that script>`. A committed project script that existed only to add
     the flag — trips had `scripts/deploy-dev.sh` — is deleted, after a grep shows nothing else calls
     it.
   - A `doppler secrets substitute` of `config/local.template.json`: set `DOPPLER_PROJECT` and
     `DOPPLER_CONFIG` from the values the wrapper read. Leave the template where it is.
   - A step that writes Doppler secrets into the app's settings file: set `SECRET_FILE` to that file,
     with `%APP_CONFIG%` for the per-OS config directory, and `SECRET_FIELDS` to the space-separated
     `dotted.path=SECRET_NAME` pairs it wrote.
   - Anything else: stop, show the user the lines, and ask where they belong. Do not drop a step
     because no setting covers it.
5. **Delete the wrapper on this machine.** It is ignored and nothing regenerates it, so show the user
   what it held and the setting each line became, then remove `scripts/deploy.sh`.
6. **Check `deploy` runs through the new path.** The shell rc's `deploy` function must read
   `deploy() { bash ~/.claude/skills/deploy/scripts/run.sh "$@"; }`; replace an older form. Then run
   `bash ~/.claude/skills/deploy/scripts/run.sh` with output redirected to a file. A dev server is a
   process with no window and runs without asking. A Tauri, IntelliJ or .NET target relaunches an
   app, so ask the user right before it, as CLAUDE.md's Taking Over the Machine section requires.
7. **Commit**, through `/adopt`'s own commit step: `config/deploy.env`, the deleted project scripts,
   and the record.
8. **Hand the other clone its half.** Its untracked `config/deploy.env` blocks the pull that brings
   the committed one, and its wrapper fails the rule. Send the repo's live session on the other
   machine one message, as the `peer` skill describes: delete `scripts/deploy.sh` and the old
   `config/deploy.env` (both already merged here), write any `config/deploy.local.env` step 3 named
   for that machine, check its shell rc's `deploy` function as step 6 does, then `/pull`.

What the deletions lose: the wrappers and the old per-machine `deploy.env` files are ignored and
exist nowhere else, so a line missed in steps 3 and 4 is gone. That is why both steps read every
line on both machines.

## When it does not apply

- **No deploy on either machine**: neither clone has a `config/deploy.env` or a `scripts/deploy.sh`.
  Check both machines; one clone without them is not evidence about the other.
- **A clone of someone else's project**, which adopts nothing.

A fork may decline this version, since it adds a file to a project its upstream owns. Its `deploy`
keeps running the per-machine wrapper.

## Continuing rule

`deploy-config-committed`: a repo with a `config/deploy.env` has it committed and naming a
`DEPLOY_TYPE`, keeps no `scripts/deploy.sh`, and commits no `config/deploy.local.env`.
