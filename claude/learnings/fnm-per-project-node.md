# Per-project Node with fnm (macOS + zsh)

`fnm env --use-on-cd` selects a Node version from `.nvmrc` / `.node-version` when you enter a directory. It
works, but four things about it are silently wrong in ways that cost hours to attribute, because each one
fails by *reporting success*.

## The prompt lies about which Node it is running

Enter a directory whose pin differs from the linked Homebrew node and fnm prints `Using Node v22.23.2` — while
`node -v` typed at that same prompt keeps answering the old version, for the life of that shell.

```
$ /bin/zsh -i -c 'cd path/to/pinned-project; echo "prompt: $(node -v)"; bash -c "echo child:  \$(node -v)"'
Using Node v22.23.2
prompt: v24.15.0        ← the shell
child:  v22.23.2        ← everything it spawns
```

**Mechanism.** fnm's hook body resolves the bare word `fnm`. With `hashdirs` on (a zsh default), that single
lookup hashes *every* entry of the Homebrew bin directory — `node` included — and it happens **before** fnm
re-points its multishell symlink. PATH's text never changes, only what the first entry points at, so zsh never
invalidates the hash it just built.

The direction is the counterintuitive part: **scripts are right and the prompt is wrong.** Anything that
re-resolves PATH — a `bash script.sh`, `/usr/bin/env node`, any `#!/usr/bin/env node` shebang — gets the
correct version. So a commit gate can pass while `node some-script.js` at the same prompt fails with a
NODE_MODULE_VERSION error. It never self-heals; `cd` away and back does not clear it, only `rehash`.

Fix — chain a second chpwd hook after fnm's (its own body can't be edited; `chpwd_functions` run in
registration order):

```zsh
eval "$(fnm env --use-on-cd --corepack-enabled --shell zsh)"
autoload -U add-zsh-hook
_fnm_rehash() { rehash }
add-zsh-hook chpwd _fnm_rehash
```

## `corepack enable` does not shim npm

`fnm env --corepack-enabled` runs plain `corepack enable` on each Node it installs, which creates yarn and pnpm
shims **but not npm**. So a `"packageManager": "npm@11.18.0"` pin is honoured by the Homebrew node (whose
`/opt/homebrew/bin/npm` *is* a corepack shim) and ignored by fnm's, which falls back to its bundled npm.

The symptom is confusing rather than obvious: `npm -v` reports a real, plausible version that simply isn't the
pinned one — and it can coincidentally equal a *sibling project's* pin, which reads like cross-project leakage
when it is just the bundled default. Each installed version needs the explicit call, once:

```bash
fnm exec --using=24 corepack enable npm
```

Note the interaction with the rehash fix above: while the hash is stale, `npm` still resolves to Homebrew's
corepack shim and the pin works by accident. Adding `rehash` moves `npm` to fnm's copy and *breaks* the pin
unless corepack is enabled there too. The two changes have to go in together.

## Agent and non-interactive shells never run the hook at all

`fnm env` lives in `~/.zshrc`, which non-interactive shells do not source. A Claude Code Bash call therefore
has empty `chpwd_functions` and gets the ambient default Node in **every** directory, whatever the `.nvmrc`
says. Adding a repo-root `.nvmrc` does not help — the hook that would read it never runs.

The only remedy in that context is to name the version explicitly:

```bash
fnm exec --using=22 -- bash .claude/commit-checks.sh
```

## A pin in a subdirectory leaves the repo root unpinned

A monorepo-ish layout with `web/.nvmrc` covers `web/`, not the repo root. Gate scripts are typically invoked
*from* the root (`bash .claude/commit-checks.sh`), so they inherit whatever the shell already had. Combined
with the previous point, a project can be fully pinned and still be built on the wrong runtime by both an
agent and a fresh terminal.

## A pin naming only a major is satisfied by more than one installed runtime

Pin the patch version wherever a test can tell two patches apart. A `.nvmrc` holding `24` is satisfied by every
installed 24.x, so which one a shell resolves decides the answer — and which one it resolves varies per shell,
by both mechanisms above.

The difference that costs most is the embedded tz database, because `Intl` reads it and nothing in a project
pins it:

| Node | `process.versions.tz` | `America/Vancouver` on 2026-12-01 |
|---|---|---|
| v24.15.0 | 2026a | PST |
| v24.19.0 | 2026b | PDT |

British Columbia moved to permanent DST in 2026b, so a test asserting a Vancouver December wall time against
UTC-8 passed three gate runs and failed the fourth with no file changed. `America/Los_Angeles` is untouched by
that release, so a suite can hold several zone assertions and have exactly one flip — which reads as a flaky
test rather than as a runtime difference.

Do not expect the abbreviation to be where it shows up. The rendered wall-clock moves with the offset, so the
same instant formats an hour apart on the two runtimes — `12:00:00 PM PST` against `1:00:00 PM PDT` — and an
assertion carrying no `timeZoneName` at all still flips. Nor is the tz database the only thing that moves with
the patch: ICU went 78.2 to 78.3 across those two, so collation and formatting output can shift on the same
upgrade. Measured 2026-10-08, and the 24 line is not special — Node 22.23.2 carries 2026a and renders Vancouver
exactly as 24.15.0 does.

Two fixes, independent of each other: pin the runtime fully so the gate is reproducible, and date every zone
assertion in the past, where the offsets are settled. A future offset is a prediction held in whichever copy of
the database the runtime was built with, and a container base image tagged by major floats the same way.

## `fnm install <major>` takes the `default` alias

If the default was deliberately aliased to `system` so fnm only overrides inside pinned projects, installing a
version silently reassigns it — `fnm list` goes from `system default` to `v24.19.0 default`. Restore with
`fnm default system`. Worth checking after any install, since nothing announces it.

## Quick diagnosis

```bash
fnm list                                   # installed versions + which holds `default`
command -v node                            # a fnm_multishells path = switched; /opt/homebrew = not
/bin/zsh -i -c 'cd <dir>; node -v; hash -r; node -v'   # differing answers = the stale-hash trap
zsh -c 'echo ${chpwd_functions:-none}'     # `none` = this shell never sources the hook
```
