---
name: deploy
description: Configure and run the LOCAL deploy — install the app on this machine or start its dev server — verifying it succeeds
disable-model-invocation: false
allowed-tools: Bash(bash ~/.claude/skills/deploy/scripts/run.sh:*), Bash(bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh:*), Bash(deploy), Bash(echo *), AskUserQuestion, Read(config/deploy.env), Write(config/deploy.env), Read(config/deploy.local.env), Write(config/deploy.local.env), Read(scripts/deploy.sh), Write(scripts/sync-db-from-prod.sh), Read(scripts/sync-db-from-prod.sh), Edit(.gitignore), Read(.gitignore), Edit(~/.bashrc), Read(~/.bashrc), Edit(~/.zshrc), Read(~/.zshrc)
---

**Scope — `deploy` is local only.** It makes the current code runnable *on this machine*: it
installs the built app locally (Tauri / IntelliJ plugin / .NET) or starts the project's local
server. It never ships anywhere public. Shipping outward is a different verb:

| Means | Where it lives |
| --- | --- |
| Run it *here*, on this machine | this skill |
| Cut a version: tag → CI → GitHub Release | the `release` skill |
| Ship it outward, to where its users are | the `publish` skill, or the project's own CI |

A project having both a local `deploy` and a publish path is normal and not a conflict — they are
separate verbs with separate scripts, so nothing outward-facing can happen from the command you run
dozens of times a day.

Which of the two publishes is a real decision, not a preference. CI builds a clean checkout with one
pinned configuration; publishing from a working tree can let uncommitted work or the wrong
environment's credentials reach production, and has. Where CI already publishes on push, the push
*is* the ship and the project should have no local publish script at all. The `publish` skill exists
for targets CI cannot reach on its own — chiefly a box you hold the SSH key for — and refuses to run
on anything not committed and pushed.

See `~/.claude/learnings/shell-environment.md` for the expected bash functions and verification checklist.

**Where the settings live.** `config/deploy.env` is committed and holds what the project decides, the same on
every clone. `config/deploy.local.env` is ignored and holds only what differs between machines; its keys override
the committed file's. The `deploy` shell function runs `~/.claude/skills/deploy/scripts/run.sh`, which reads
`DEPLOY_TYPE` and calls the target script — there is no per-repo wrapper. Every key a target reads is listed in
that target script's header.

## Context
- Deploy function in shell rc: !`cat ~/.bashrc ~/.zshrc ~/.bash_profile ~/.zprofile 2>/dev/null | grep -c "deploy()" || echo 0`
- Deploy function calls run.sh: !`cat ~/.bashrc ~/.zshrc ~/.bash_profile ~/.zprofile 2>/dev/null | grep -c "skills/deploy/scripts/run.sh" || echo 0`
- Shell rc target: !`case "$(uname -s)" in Darwin) echo "~/.zshrc" ;; MINGW*|MSYS*|CYGWIN*) echo "~/.bashrc" ;; *) [ -n "$ZSH_VERSION" ] || [ "${SHELL##*/}" = "zsh" ] && echo "~/.zshrc" || echo "~/.bashrc" ;; esac`
- Legacy wrapper exists (scripts/deploy.sh): !`test -f scripts/deploy.sh && echo yes || echo no`
- Convention record: !`grep -v '^#' .claude/conventions 2>/dev/null | head -1 || echo none`
- Deploy settings ignored by git: !`git check-ignore -q config/deploy.env && echo yes || echo no`
- Static web entry (index.html): !`(ls index.html web/index.html public/index.html src/index.html dist/index.html 2>/dev/null | grep -q .) && echo yes || echo no`
- Static web dir (dir holding index.html; empty if none): !`for d in . web public src dist; do [ -f "$d/index.html" ] && { echo "$d"; break; }; done; true`
- Project start script (a committed scripts/dev.sh the project already provides): !`test -f scripts/dev.sh && echo yes || echo no`
- Production deployment (config/publish.env with SSH_HOST): !`grep -q '^SSH_HOST=' config/publish.env 2>/dev/null && echo yes || echo no`
- Prod sync script (scripts/sync-db-from-prod.sh): !`test -f scripts/sync-db-from-prod.sh && echo yes || echo no`
- Configured DEPLOY_TYPE: !`grep -m1 '^DEPLOY_TYPE=' config/deploy.env 2>/dev/null || echo none`
- Dev-server dir (package.json with a 'dev' script; empty if none): !`for d in . web app apps/web client frontend site www server; do [ -f "$d/package.json" ] && node -e "p=require('./'+process.argv[1]+'/package.json');process.exit(p.scripts&&p.scripts.dev?0:1)" "$d" 2>/dev/null && { echo "$d"; break; }; done; true`
- Dev-server start command guess: !`for d in . web app apps/web client frontend site www server; do [ -f "$d/package.json" ] || continue; node -e "p=require('./'+process.argv[1]+'/package.json');process.exit(p.scripts&&p.scripts.dev?0:1)" "$d" 2>/dev/null || continue; if [ -f "$d/pnpm-lock.yaml" ]; then echo "pnpm dev"; elif [ -f "$d/yarn.lock" ]; then echo "yarn dev"; elif [ -f "$d/bun.lockb" ]; then echo "bun run dev"; else echo "npm run dev"; fi; break; done; true`
- Dev-server port guess (from the dev script; empty if none found): !`for d in . web app apps/web client frontend site www server; do [ -f "$d/package.json" ] || continue; node -e "p=require('./'+process.argv[1]+'/package.json');s=(p.scripts&&p.scripts.dev)||'';m=s.match(/(?:-p|--port[= ])\s*(\d{2,5})/);if(m)console.log(m[1]);process.exit(s?0:1)" "$d" 2>/dev/null && break; done; true`
- Deploy env: !`cat config/deploy.env 2>/dev/null || echo MISSING`
- Deploy local env: !`cat config/deploy.local.env 2>/dev/null || echo MISSING`
- Deploy env has CONFIG_DEST: !`grep -c '^CONFIG_DEST=' config/deploy.env 2>/dev/null || echo 0`
- Tauri project: !`test -f src-tauri/tauri.conf.json && echo yes || echo no`
- Tauri identifier: !`sed -n 's/.*"identifier"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' src-tauri/tauri.conf.json 2>/dev/null | head -1 || echo none`
- Secret config template present (config/local.template.json): !`test -f config/local.template.json && echo yes || echo no`
- Deploy env has DOPPLER_PROJECT: !`grep -c '^DOPPLER_PROJECT=' config/deploy.env 2>/dev/null || echo 0`
- .NET project: !`ls src/*.csproj 2>/dev/null | grep -q . && echo yes || echo no`
- IntelliJ plugin project: !`(test -f build.gradle.kts || test -f build.gradle) && grep -lE 'org\.jetbrains\.intellij(\.platform)?' build.gradle.kts build.gradle 2>/dev/null | grep -q . && echo yes || echo no`
- IntelliJ plugins-dir guess: !`bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh plugins-dir 2>/dev/null || echo`
- IntelliJ IDE exe guess: !`bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh ide-exe 2>/dev/null || echo`
- IntelliJ IDE process guess: !`bash ~/.claude/skills/deploy/scripts/detect-intellij-target.sh ide-process 2>/dev/null || echo`
- Deploy local env has IDE_PROCESS: !`grep -c '^IDE_PROCESS=' config/deploy.local.env 2>/dev/null || echo 0`
- Deploy local env has IDE_EXE: !`grep -c '^IDE_EXE=' config/deploy.local.env 2>/dev/null || echo 0`

## 1. Detect project type

If **Legacy wrapper exists** is yes and **Convention record** is below 17 (or none), this repo has not adopted
convention 017: its settings may be split across machines and its wrapper may hold steps of its own. Do not
configure it here. Tell the user to run `/adopt` in this repo, which merges both machines' settings into the
committed file, and stop.

Pick `DEPLOY_TYPE` — and the target script it names — from the **Context** flags. An already-configured
**Configured DEPLOY_TYPE** wins first (a prior run picked it):

- `dev-server` → `deploy-dev-server.sh` (§2a)
- `tauri` → `deploy-tauri.sh`
- `intellij-plugin` → `deploy-intellij-plugin.sh`
- `dotnet` → `deploy.sh`

Otherwise detect it:

- **Tauri project** is yes → `tauri`
- else **IntelliJ plugin project** is yes → `intellij-plugin`
- else **.NET project** is yes → `dotnet`
- else **Dev-server dir** is non-empty (a `package.json` with a `dev` script — Next.js, Remix, SvelteKit, Vite, a plain Node server) → `dev-server` (§2a)
- else **Static web entry (index.html)** is yes (a static site with no `dev` script — plain HTML/JS served from a directory) → `dev-server` (§2a), configured as a static file server
- else → **STOP**. Tell the user:
  > The `deploy` skill recognizes Tauri (`src-tauri/tauri.conf.json`), IntelliJ plugins (`build.gradle[.kts]` using `org.jetbrains.intellij[.platform]`), .NET (`src/*.csproj`), and local web servers (a `package.json` with a `dev` script, or a static `index.html`). None was found in the current directory. If this is a different stack, add a new underlying script in `~/.claude/skills/deploy/scripts/` and extend the skill.
  >
  > If you meant to ship this somewhere public, that isn't `deploy`: a site goes live through the project's CI pipeline, and a versioned artifact through the `release` skill.

  Do not create `config/deploy.env`. Exit.

A project that also ships to a public host is not a conflict — `deploy` configures the local
side only, and CI handles shipping. Never ask the user to choose between the two. If
more than one *local* target's flag is yes (mixed repo), ask which one `deploy` should mean —
do not guess.

## 2. Check prerequisites

1. If **Deploy function calls run.sh** is 0, the `deploy` function in the file in **Shell rc target** (`~/.zshrc` on macOS, `~/.bashrc` on Windows Git Bash / Linux-bash) is missing or an older form. Replace an existing `deploy()` line, or append one when **Deploy function in shell rc** is 0:
   ```bash
   deploy() { bash ~/.claude/skills/deploy/scripts/run.sh "$@"; }
   ```
   `run.sh` finds the project root itself by walking up to `config/deploy.env`, so `deploy` works from any subdirectory. Leave a `run_repo_script` helper in place: the `build` skill and others still call it.

Every key below goes into `config/deploy.env` unless it says `config/deploy.local.env`. Write `DEPLOY_TYPE=<the type from step 1>` first, always. Ask only for keys neither **Deploy env** nor **Deploy local env** already holds.

**If the type is `dev-server`, configure via §2a and skip items 2–4. (Items 2–4 are for the local-install targets.)**

### 2a. Local web server configuration

For a local web server, `deploy` stops whatever holds the port and relaunches the start command detached (so it outlives the Claude session), then waits for the port to come up. Write `config/deploy.env` with these keys (ask only for keys not already present; use the Context-derived defaults — confirm them with the user rather than asking blind):

- `DEPLOY_TYPE=dev-server` — always; `run.sh` dispatches on it.
- `DEV_DIR=` — the directory `DEV_CMD` is **run from** (not necessarily the one being served), relative to repo root; logs are written here too. Decide it together with `DEV_CMD` below:
  - using the project's own `scripts/dev.sh` → `.`, since that path is repo-root-relative and the script decides for itself what to serve. Setting this to the web dir instead makes the command not found.
  - using a package-manager `dev` script → the **Dev-server dir** Context value (`.` for a root app, `web` for a monorepo subdir).
  - serving a static directory directly → the **Static web dir** value.
- **No `DEV_PORT` key.** The port comes from the ports registry, which the script asks on every run under the use case `ports.py dev-use-case` derives. Write nothing about it here, and delete the line from a `deploy.env` that still has one — it is read by nothing and is the second copy the registry exists to remove. Before configuring, record the project's port if the registry does not hold it yet: `python3 ~/.claude/skills/ports/scripts/ports.py allocate --use-case <use-case> --owner <owner> --notes "<what starts it>"`, where `<use-case>` is what `ports.py dev-use-case --from <repo root>` prints and `<owner>` what the same command prints with `--owner` added — the script asks exactly those, so the record is the claim it reads; never spell either by hand. Add `--port <n>` when the project's dev script already pins a number, so the record matches what it actually takes. The **Dev-server port guess** Context value is evidence for that `--port`, never the answer on its own. **If the port is fixed for an external reason** (an API key restricted to `http://localhost:<port>`, an OAuth redirect URI, a CORS allowlist), add `--pinned "<why this number and no other>"` — that is what stops the allocator moving it and what lets the v15 rule allow the literal the project cannot remove. Where the registry already holds the claim, the reason goes on with `ports.py amend --use-case <slug> --pinned "<why>"`; `allocate` refuses to write to a claim it found.
- `DEV_CMD=` — command that starts the server. Derive the default:
  - if **Project start script** is yes → `bash scripts/dev.sh` — prefer the project's own committed starter, which may do setup the skill can't know about (rendering a gitignored config, fetching a token). It runs in the foreground and this target detaches it, which is the right shape.
  - else if **Dev-server dir** is non-empty → **Dev-server start command guess** Context value (picks `pnpm`/`yarn`/`bun`/`npm` from the lockfile). Keep it as the package-manager script (e.g. `npm run dev`) even when that script itself wraps another tool (Doppler, env loaders) — the wrapping lives in `package.json`, not here.
  - else (static site, no `dev` script) → `python -m http.server "$PORT" --directory <DEV_DIR>` — the script exports `PORT` with the registry's number before launching, so a command that reads it needs no literal. A server that ignores `PORT` and takes the port as an argument has to be given one; record it `--pinned` with that as the reason, since the project cannot resolve it at launch.
- `DEV_TAILNET=` — **only written as `DEV_TAILNET=no`, for a project whose origin is pinned to localhost** (an API key restricted to `http://localhost:<port>`, an OAuth redirect URI, a CORS allowlist — the same reasons that pin a port in the registry). The tailnet name would fail that check, so the script prints the `localhost` URL and publishes nothing. Leave it out otherwise. A dev server that checks the `Host` header (Vite's `server.allowedHosts`) needs the node's MagicDNS name allowed instead; that is a project config change, not this key. Next's dev server refuses its `/_next` assets rather than the request, so the page arrives and never hydrates, with no refused request to read in the log; `~/.claude/learnings/nextjs16-prisma7-scaffold.md` carries the `allowedDevOrigins` pattern that answers it.
- `DEV_PRESTART_CMD=` — **optional, and only written when the user asks for one.** A command run from the
  repo root between stopping the old server and launching the new one: fetching a fixture, rendering a
  generated file. Leave the key out entirely when there is no such step; an empty value and an absent one
  behave identically, but an absent one does not invite an editor to fill it in. Copying production data
  into the local database is **not** a pre-start step: it runs on every deploy, so a plain `deploy` would
  reach production. That job is `DEV_DB_SYNC_CMD`, which the **Production data sync** paragraph of §2a
  sets up.

  **The command belongs to the project, not here.** Write it as a committed script in the repo
  (`scripts/<verb>.sh`) and point this key at it, so the knowledge of *how* a project seeds its database —
  the container names, the host, the tool versions — stays in the repo that has it, and the global script
  stays a thing every stack can use. Never put a stack's specifics behind another key in this file.

  The gap between stop and launch is the whole reason the hook sits where it does: a step that replaces
  state the app holds open — dropping and restoring a database being the clear case — cannot run safely
  while the server is up. A failure does **not** stop the launch, because `deploy` is what leaves the app
  runnable and a pre-start step is usually the part needing something beyond this machine; it is reported
  at the point of failure and again beside the URL.
- `DEV_DB_SYNC_CMD=` — **optional.** The command `deploy --db` runs, replacing the local data with
  production's; a plain `deploy` never runs it, so it never reaches production unasked. It runs in the same
  gap as `DEV_PRESTART_CMD`, before it, and follows the same rules: a committed project script, a failure
  that still restarts the server and is repeated beside the URL. The **Production data sync** paragraph
  below says when to offer it.

**Production data sync (`--db`).** When **Production deployment** is yes and **Deploy env** names no
`DEV_DB_SYNC_CMD`, ask whether `deploy --db` should replace the local dev database with production's before
restarting. Say in the question that it destroys whatever exists only in the local database, and that a
plain `deploy` stays offline either way. On no, skip it. On yes, write `DEV_DB_SYNC_CMD=bash
scripts/<sync-script>.sh`. If **Prod sync script** is no, the project needs a committed
`scripts/sync-db-from-prod.sh` (or an existing script under another name, if it already has one) that:
- reads the box's address from `config/publish.env` (`SSH_HOST`) rather than repeating it;
- copies one way only, production to local, and never writes to production;
- starts and migrates the dev database itself, so `deploy` needs no other step;
- replaces the local data in one transaction, or through the app's own importer, and fails loudly on a
  mismatch.

For a SQL database, `~/.claude/learnings/copy-prod-db-to-dev.md` is the procedure, including the traps a
short script falls into (a streamed dump that commits half a database, a count read that compares nothing).
The scheduler repo's `scripts/seed-dev-from-prod.sh` (`pg_dump --data-only` over SSH, truncate and load in
one transaction) implements it. For an app that restores through its own importer, the trips repo's
`scripts/sync-db-from-prod.sh` shows the importer half: take the restore from it, and hold the rest to the
requirement list above, whatever its starting and wiring look like at the time. Read whichever matches the
stack before writing a third. The stack's specifics stay in that script, never in `config/deploy.env`.

`config/deploy.env` holds no secrets and is committed, so every clone runs the same `deploy`. The dev server writes `dev-server.log` / `dev-server.err.log` into `DEV_DIR` — ensure those are gitignored: if `<DEV_DIR>/dev-server*.log` (or a broader `dev-server*.log`) isn't already covered by `.gitignore`, add it. After writing the config, go to **step 3**.

**Local-install targets (Tauri / IntelliJ / .NET) — items 2–4:**

2. **Install location.**
   - **Tauri / .NET** — write no `INSTALL_DIR` when the per-OS default fits: `/Applications` on macOS, `C:/Programs/<binary name>` on Windows (the Cargo package name, or the .NET assembly name). Ask only whether that default is right; if the user wants another location, write `INSTALL_DIR` to `config/deploy.local.env`, since any one path is right on one OS only.
   - **IntelliJ plugin** — the plugins directory names the IDE version, which differs per machine, so write `INSTALL_DIR` to `config/deploy.local.env`. Use the **IntelliJ plugins-dir guess** Context value verbatim (it already emits the cross-platform `%APP_CONFIG%/JetBrains/<dir>/plugins` form). If empty (JetBrains dir not found), fall back to `%APP_CONFIG%/JetBrains/IntelliJIdea<newest>/plugins` and ask the user to verify. `%APP_CONFIG%` resolves to `~/AppData/Roaming` on Windows and `~/Library/Application Support` on macOS at deploy time; the legacy `%APPDATA%` placeholder is also accepted as an alias.

   Then apply the stack-specific follow-up questions:
   - **Tauri** — if **Deploy env has CONFIG_DEST** is 0 and the project ships a config (`config/local.json` or `config/local.template.json`), ask where the app reads it (default: `%APP_CONFIG%/<Tauri identifier>/config.json` — substitute **Tauri identifier**; use forward slashes) and write `CONFIG_DEST=<their answer>`. This is the path the app actually reads (`app_data_dir()`), not the install dir. The deploy refuses to run when a config exists and `CONFIG_DEST` does not.

     **Secrets via Doppler (optional).** Two forms; pick by who owns the settings file. Either way, ask for the Doppler project and config (skip if **Deploy env has DOPPLER_PROJECT** ≥ 1) and write `DOPPLER_PROJECT=<name>` and `DOPPLER_CONFIG=<name>` — they are coordinates, not secrets. An app with no Doppler home yet gets a **config** inside an existing project — `dev_<app>` in the `local` project for a workstation-only app — never a project of its own; invoke `/doppler` rather than inventing names here.
     - **The project owns the whole config** (it is `config/local.json`, copied over whatever the app had): keep `config/local.template.json` with `{{tojson .SECRET_NAME}}` placeholders and literal values for the rest. `deploy-tauri.sh` renders it into a temporary file, copies that to `CONFIG_DEST` and deletes it, so no plaintext copy sits in the repo. The signal: **Secret config template present** is yes, or `config/local.json` carries tokens.
     - **The app owns its settings** (it writes them as the user works, so overwriting would lose them): write `SECRET_FILE=<the settings file, with %APP_CONFIG%>` and `SECRET_FIELDS=<dotted.path=SECRET_NAME ...>`, space-separated. The deploy writes those fields into the existing file while the app is stopped and leaves every other value as the app saved it.

     Skip all of this when the project has no secrets.
   - **IntelliJ plugin** — also ask (optional, skippable) for `IDE_PROCESS` (default = **IntelliJ IDE process guess** Context value) and `IDE_EXE` (default = **IntelliJ IDE exe guess** Context value; if empty — e.g. Toolbox-managed IDE, or running on macOS where the script doesn't auto-detect — offer to skip). On macOS, optionally ask for `IDE_BUNDLE_ID` (e.g. `com.jetbrains.intellij.ce`) — when set, the deploy uses `osascript … to quit` instead of `pkill`. Write each key the user confirms to `config/deploy.local.env`. Skipping is fine — the deploy still works, it just won't stop/restart the IDE.
3. If **Deploy env** is present, the project is **Tauri**, ships a config, and **Deploy env has CONFIG_DEST** is 0, ask for `CONFIG_DEST` as above.
4. If the project is an **IntelliJ plugin** and **Deploy local env has IDE_PROCESS** / **IDE_EXE** are 0, ask the user whether to add them (using the same Context-derived guesses as defaults) and write any values they supply to `config/deploy.local.env`.

## 3. Make the settings committable

1. If **Deploy settings ignored by git** is yes, something hides `config/deploy.env`. Run `git check-ignore -v config/deploy.env` to name the file and line. A `config/deploy.env` line in the global excludes means this machine's dotfiles predate convention 017 — tell the user to pull the dotfiles repo. A line in the project's `.gitignore` gets removed. Do not commit the file yourself; it goes in with the rest of the user's work.
2. Confirm `config/deploy.local.env`, when written, is ignored: `git check-ignore -q config/deploy.local.env` must exit 0. The global excludes carry it; if they do not, the dotfiles need pulling too.

## 4. Deploy

If step 2 changed the shell rc, tell the user:
> The `deploy` shortcut has been configured. **Restart Claude Code** for `! deploy` to work — the shell reads its rc file only at startup, so new functions aren't available until the next session.

When the type starts, restarts or closes an app with a window — `dotnet` and `tauri` both launch the installed app, and `intellij-plugin` closes the IDE when `IDE_PROCESS` or `IDE_BUNDLE_ID` is set — ask right before running it, per CLAUDE.md's **Taking Over the Machine**: name the app that will start, restart or close, and run only on a yes. `dev-server` starts no window and needs no ask.

Run the deploy now, through the same entry point the shell function uses, with output redirected to a file rather than piped (a detached dev server can hold a pipe open):
```
bash ~/.claude/skills/deploy/scripts/run.sh > tmp/deploy.log 2>&1
```

Report the output to the user. If it fails, analyze the error and suggest a fix. On success, remind the user to restart Claude Code if they haven't already, then `! deploy` will work.

**For a `dev-server` deploy, state the URL in the report — written out in full, exactly as the script's last line (`open: …`) prints it.** That is the tailnet address, which the script gets from `~/.claude/skills/shared/tailnet_publish.py publish-port` so the link opens on every machine the user has. **Its port is not the one the server listens on** — the script allocates a separate front port from the ports registry and fronts the dev server from there, because a `tailscale serve` mapping holds the wildcard address and one on the server's own port would stop it rebinding at the next restart. It prints the `http://localhost:<port>` form instead, with the reason, when publishing fails or `DEV_TAILNET=no`, and the report carries that reason along with the address. Not a port number in isolation, not implied by a config value, not buried inside `curl` output: an address someone can click. It costs one clause and it is the difference between the user looking at the thing and the user asking where it is. Then let them look — do not screenshot a page they can open themselves, at better fidelity than a screenshot, in less time than the round-trip takes.

**A deploy overwrites the installed config — warn before running one.** When `config/local.json` or `config/local.template.json` exists, the deploy copies it over the installed `config.json`, so anything the *app itself* wrote there at runtime — an API key typed into an in-app settings dialog, an OAuth token — is destroyed, silently, if `local.json` carries an empty placeholder for that field. Nothing in the output says a value was lost. Before deploying an app that persists its own settings to the installed config, check `local.json` for empty credential fields and tell the user; the repo's `local.json` is the source of truth, so that is where their keys belong. An app that owns its settings this way is the case `SECRET_FILE` and `SECRET_FIELDS` exist for.
