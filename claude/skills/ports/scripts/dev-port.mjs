// Resolve a project's port from the ports registry and run its server with PORT set, so the number
// exists in exactly one place. A library: the project's own `scripts/dev.mjs` imports `run` from it.
//
// A port written into a dev script is a copy that nothing reconciles, and the copy is what the process
// reads. Resolving it here instead makes the absence of a literal the proof that the port came from the
// registry — which is the whole reason a repo can be checked for this with a grep.
//
// Node rather than Python because an npm script's command line is the one place a platform split bites:
// npm runs scripts through sh on POSIX and cmd.exe on Windows, so neither `python3` nor a `~` path
// survives both. Node is already a dependency of every project that has a dev script, and it can find
// the home directory and the right interpreter itself.
//
// Called by a committed `scripts/dev.mjs` in each project, which supplies the use case and the command:
//
//     import { run } from '<this file>'
//     await run({ useCase: 'scheduler-dev-server', owner: 'scheduler', command: process.argv.slice(2) })
//
// Next, Vite and most servers read PORT from the environment. Next classifies an env-supplied port as
// source `env` rather than `default`, which keeps its retry-on-collision path off — so the server binds
// the allocated number or exits, instead of drifting silently to the next free one.

import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const PORTS_PY = join(homedir(), '.claude', 'skills', 'ports', 'scripts', 'ports.py')

function fail(message) {
  console.error(`dev-port: ${message}`)
  process.exit(1)
}

/** The port the registry holds for `useCase`, assigning one on the first call. */
function resolvePort({ useCase, owner, notes }) {
  if (!existsSync(PORTS_PY)) {
    fail(`${PORTS_PY} is not there. This project's port comes from the claude dotfiles' ports registry, `
       + `which is not installed on this machine — install it and retry, or read the port out of the `
       + `registry by hand and run the server with PORT=<n> set.`)
  }
  const python = process.platform === 'win32' ? 'python' : 'python3'
  const result = spawnSync(python, [
    PORTS_PY, 'allocate',
    '--use-case', useCase,
    '--owner', owner,
    '--notes', notes || `Resolved at launch by ${owner}'s scripts/dev.mjs; the number is not in this repo.`,
  ], { encoding: 'utf-8', stdio: ['ignore', 'pipe', 'inherit'] })

  if (result.error) fail(`could not run ${python}: ${result.error.message}`)
  if (result.status !== 0) fail(`${PORTS_PY} allocate exited ${result.status} for '${useCase}' — reason above.`)
  const port = (result.stdout || '').trim()
  if (!/^\d{2,5}$/.test(port)) fail(`allocate printed ${JSON.stringify(port)} rather than a port number.`)
  return port
}

/** Resolve the port, then exec `command` with PORT set. Exits with the command's own status. */
export async function run({ useCase, owner, notes, command }) {
  if (!command || command.length === 0) fail('no command given — usage: dev.mjs <command> [args...]')
  const port = resolvePort({ useCase, owner, notes })
  console.error(`dev-port: ${useCase} -> ${port}`)
  // shell:true on Windows: npm-installed binaries are .cmd shims there, which CreateProcess will not run.
  const child = spawnSync(command[0], command.slice(1), {
    env: { ...process.env, PORT: port },
    stdio: 'inherit',
    shell: process.platform === 'win32',
  })
  if (child.error) fail(`could not run ${command.join(' ')}: ${child.error.message}`)
  process.exit(child.status === null ? 1 : child.status)
}
