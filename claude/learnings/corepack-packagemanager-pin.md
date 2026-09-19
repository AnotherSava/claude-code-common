# Pinning the package manager with packageManager + Corepack

Pin a Node project's package-manager version so every machine and CI run uses an identical
manager — otherwise the lockfile drifts whenever two machines run different npm versions.

## The drift symptom

Running `npm install` on machine B after machine A committed the lockfile produces a large
diff that touches no real dependencies — only metadata: `"peer": true` markers added/removed,
`"devOptional"` flipped to `"dev"`, optional packages (e.g. `@emnapi/*`) pruned or restored.
This is purely an npm-version difference (npm 11+ writes `peer: true`; older npm doesn't).

Fix the immediate churn by discarding it (`git checkout -- package-lock.json`) and keeping the
committed lockfile as the source of truth; then pin the manager so it can't recur.

## The pin

In `package.json`:

```json
"packageManager": "npm@11.17.0"
```

Then enable Corepack once per machine. Corepack reads `packageManager` and shims the manager to
exactly that version regardless of what's globally installed.

**npm is a deliberate exception:** plain `corepack enable` does NOT shim `npm` (only yarn/pnpm) —
so the pin is silently ignored and `npm -v` keeps reporting the bundled version. You must enable
npm explicitly:

```
corepack enable npm
```

Verify it took: `npm -v` inside the project should report the pinned version (first call may pause
to download it). yarn/pnpm need only plain `corepack enable`: `"packageManager": "pnpm@9.x.x"`, etc.

Caveat: Corepack's npm support is the least battle-tested of the three (known "version doesn't
switch" reports; a `COREPACK_ENABLE_AUTO_PIN=0` workaround exists). If it misbehaves, the fallback
is to treat `packageManager` as metadata (CI's `actions/setup-node` still honors it) and align the
local npm manually with `npm install -g npm@<version>` on each machine.

## Windows gotcha: `corepack enable` needs admin

`corepack enable` (and `corepack enable npm`) writes its shims into the Node install's bin dir. If
Node lives in a protected location (e.g. `C:\Program Files\nodejs\`),
it fails with:

```
Internal Error: EPERM: operation not permitted, open 'C:\...\nodejs\pnpx'
```

Run it from an **elevated** (Run as administrator) PowerShell. An agent can raise that itself with
`Start-Process … -Verb RunAs -Wait`, which puts a UAC prompt on the user's desktop rather than a
command in their lap — ask immediately before, since the prompt interrupts whatever they are doing,
then run it. Redirect inside the elevated process (`-RedirectStandardOutput` is rejected alongside
`-Verb RunAs`), and prefer `powershell -Command` over `cmd /c` as the elevated shell: cmd's quoting
rules around `/c "…" > file` swallow the redirect and exit 1 with no output. Alternative without
admin: `corepack enable --install-directory <a writable dir already on PATH>`.

## Upgrading Node silently un-pins the manager

**Re-run `corepack enable npm` after every Node upgrade**, before trusting the pin again. The
upgrade replaces the Node install directory and takes corepack's shims with it, so `npm -v` quietly
goes back to answering with the bundled npm and `packageManager` stops being enforced.

Nothing reports it. There is no error, the install still works, and a conventions rule asserting the
pin's *shape* — that the field exists and matches `npm@x.y.z` — passes exactly as before, because
the field is untouched; it is the machine that stopped honouring it. The only honest check is
`npm -v` inside the project, compared against the field.

Measured 2026-09-18 on Windows: `winget upgrade --id OpenJS.NodeJS.LTS` took Node 24.13.0 to
24.19.0 and `npm -v` went from the pinned 12.0.2 to the bundled 11.17.0 in the same breath.

The same upgrade **kills every running Node process's tooling**. Replacing `node.exe` ended all nine
MCP servers belonging to three live Claude Code sessions — the expectation that a running process
keeps its already-mapped image is wrong here. Check what is running first, and expect any editor or
agent session relying on a Node-based server to need a restart afterwards.

## It freezes until you bump it — that's the point

The pin does NOT auto-update; Corepack uses exactly the pinned version forever until you edit the
field and commit. That's deliberate (reproducibility). Bump it like a dependency: change the
version, run `npm install` once to regenerate the lockfile with the new manager, commit both.
The new version propagates to other machines on their next pull.

Sane bump cadence (npm isn't security-sensitive — no urgency):
- when bumping the Node version (take whatever ships with it, or current stable),
- when a specific bug is fixed in a newer manager,
- an occasional "catch up to latest stable" sweep.

## Finding the current stable npm

```
npm view npm version          # the `latest` dist-tag → current stable
npm view npm dist-tags --json # shows next-N tags; a `next-12: 12.0.0-pre.1` means 12 is prerelease — don't pin to it
```

Read the answer rather than carrying one: npm's stable major moves, and a version written here is
wrong on a schedule. Measured 2026-09-18, `npm view npm version` answered `12.0.2`, where a note
from June 2026 in this file had said npm 12 was prerelease only.

**Check the pinned npm runs on the Node the project targets.** npm 12 requires
`^22.22.2 || ^24.15.0 || >=26.0.0`, so a project on an earlier Node 24 patch needs an npm 11 pin
instead — and the mismatch is a warning on every command rather than a refusal, so it persists
quietly.
