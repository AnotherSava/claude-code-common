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
Node lives in a protected location (e.g. `C:\programming\nodejs\` or `C:\Program Files\nodejs\`),
it fails with:

```
Internal Error: EPERM: operation not permitted, open 'C:\...\nodejs\pnpx'
```

Run it from an **elevated** (Run as administrator) PowerShell. Cannot self-elevate from the
agent — ask the user to run `corepack enable npm` in an admin shell. Alternative without admin:
`corepack enable --install-directory <a writable dir already on PATH>`.

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

As of June 2026: npm 11 is the current stable major (latest `11.17.0`), shipped with the Node 24
LTS line; npm 12 is prerelease only.
