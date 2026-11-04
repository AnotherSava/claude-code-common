// Resolve a project's port from the ports registry and run its server with PORT set, so the number
// exists in exactly one place.
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
// Run as a command, through the `dev-port` launcher in ../bin that the dotfiles install puts on PATH:
//
//     "dev": "dev-port next dev"
//
// The use case comes from `ports.py dev-use-case`, which deploy-dev-server.sh asks too, so `npm run dev` by
// hand and `deploy` ask the registry for the same claim. A repo that still carries a `scripts/dev.mjs`
// imports `run` from here with the two names spelled out instead.
//
// Next reads PORT from the environment, and classifies an env-supplied port as source `env` rather than
// `default`, which keeps its retry-on-collision path off — so the server binds the allocated number or
// exits, instead of drifting silently to the next free one.
//
// **Vite does not read PORT, and a project served by it needs one more line than this.** Measured
// 2026-10-06 across six installed copies, vite 6.4.1 through 8.2.1: no file under `vite/dist/` matches
// `env.PORT` at all. Its `server.port` comes from config only, so exporting PORT here and deleting the
// `-p` literal leaves Vite on its own 5173 — a worse state than the literal, because the registry then
// records a number nothing binds. Such a project's `vite.config.ts` has to read `process.env.PORT`
// itself, and should refuse to start without it rather than falling back to a default.

import { spawnSync } from 'node:child_process'
import { lstatSync, realpathSync, statSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const PORTS_PY = join(homedir(), '.claude', 'skills', 'ports', 'scripts', 'ports.py')

function fail(message) {
  console.error(`dev-port: ${message}`)
  process.exit(1)
}

/** Which of three states `PORTS_PY` is in: `present`, `absent`, or `unreadable` with the reason. */
function registryScript() {
  let linked = true
  try { lstatSync(PORTS_PY) } catch (error) {
    if (error.code === 'ENOENT') linked = false
    else return { state: 'unreadable', why: `could not be read (${error.code})` }
  }
  try { statSync(PORTS_PY) } catch (error) {
    if (error.code !== 'ENOENT') return { state: 'unreadable', why: `could not be read (${error.code})` }
    if (linked) return { state: 'unreadable', why: 'is a symlink resolving to nothing, so the dotfiles checkout it points into has moved or been removed' }
    return { state: 'absent' }
  }
  return { state: 'present' }
}

const PYTHON = process.platform === 'win32' ? 'python' : 'python3'

/** Exit with the right instruction unless the registry script can be run. */
function requireRegistry() {
  // One `existsSync` cannot carry this message: it answers false for a path that is missing and for a
  // symlink resolving to nothing alike, and this path runs through `~/.claude/`, a tree symlinked out of the
  // dotfiles checkout — so moving that checkout produces the second state and the first one's wording sends
  // the reader to install what is already installed. Errno table in
  // `~/.claude/learnings/absence-versus-unreadable.md`.
  const found = registryScript()
  if (found.state === 'absent') {
    fail(`${PORTS_PY} is not there. This project's port comes from the claude dotfiles' ports registry, `
       + `which is not installed on this machine — install it and retry, or read the port out of the `
       + `registry by hand and run the server with PORT=<n> set.`)
  }
  if (found.state === 'unreadable') {
    fail(`${PORTS_PY} ${found.why}. That is a repair rather than an install: the dotfiles' install block `
       + `re-creates the link, or read the port out of the registry by hand and run the server with `
       + `PORT=<n> set.`)
  }
}

/** The port the registry holds for `useCase`, assigning one on the first call. */
function resolvePort({ useCase, owner, notes }) {
  requireRegistry()
  const result = spawnSync(PYTHON, [
    PORTS_PY, 'allocate',
    '--use-case', useCase,
    '--owner', owner,
    '--notes', notes || `Resolved at launch by ${owner}'s dev script; the number is not in that repo.`,
  ], { encoding: 'utf-8', stdio: ['ignore', 'pipe', 'inherit'] })

  if (result.error) fail(`could not run ${PYTHON}: ${result.error.message}`)
  if (result.status !== 0) fail(`${PORTS_PY} allocate exited ${result.status} for '${useCase}' — reason above.`)
  const port = (result.stdout || '').trim()
  if (!/^\d{2,5}$/.test(port)) fail(`allocate printed ${JSON.stringify(port)} rather than a port number.`)
  return port
}

/** `argv` as one cmd.exe command line, quoting every token the shell would otherwise split or interpret. */
function windowsCommandLine(argv) {
  return argv.map((arg) => {
    if (arg.includes('"')) fail(`cannot run ${JSON.stringify(arg)} through cmd.exe — an embedded double quote has no escape that survives \`cmd /d /s /c\`. Put the value in a file the command reads instead.`)
    return /[\s&|<>^()]/.test(arg) ? `"${arg}"` : arg
  }).join(' ')
}

/** What ports.py records a dev server launched from `start` under: its use case, or with `--owner` its owner. */
function devClaim(start, ...flags) {
  const result = spawnSync(PYTHON, [PORTS_PY, 'dev-use-case', '--from', start, ...flags], { encoding: 'utf-8', stdio: ['ignore', 'pipe', 'inherit'] })
  if (result.error) fail(`could not run ${PYTHON}: ${result.error.message}`)
  const answer = (result.stdout || '').trim()
  if (result.status !== 0 || !answer) fail(`${PORTS_PY} dev-use-case exited ${result.status} for ${start} — reason above.`)
  return answer
}

/** Run `command` on the port the registry holds for the project the working directory belongs to. */
export async function runHere(command) {
  if (!command || command.length === 0) fail('no command given — usage: dev-port <command> [args...]')
  requireRegistry()
  const useCase = devClaim(process.cwd())
  await run({ useCase, owner: devClaim(process.cwd(), '--owner'), command,
              notes: `Resolved at launch by dev-port for ${useCase}; the number is not in that repo.` })
}

/** Resolve the port, then exec `command` with PORT set. Exits with the command's own status. */
export async function run({ useCase, owner, notes, command }) {
  if (!command || command.length === 0) fail('no command given — usage: dev-port <command> [args...]')
  const port = resolvePort({ useCase, owner, notes })
  console.error(`dev-port: ${useCase} -> ${port}`)
  // Windows needs a shell at all: npm-installed binaries are `.cmd` shims there, which CreateProcess will
  // not run. But Node concatenates an argv array under that flag with no escaping — the DEP0190 warning
  // says so — and cmd.exe then re-splits on the spaces, so a checkout under `C:\Users\First Last\` fails
  // naming half a path and nothing about a port. Handing it one already-quoted line is the form that
  // reaches the shim and survives the split: Node wraps it as `cmd /d /s /c "<line>"`, and `/s` strips
  // only that outer pair, leaving these quotes standing. POSIX needs no shell and so keeps the argv array,
  // where no quoting question arises.
  const options = { env: { ...process.env, PORT: port }, stdio: 'inherit' }
  const child = process.platform === 'win32'
    ? spawnSync(windowsCommandLine(command), { ...options, shell: true })
    : spawnSync(command[0], command.slice(1), options)
  if (child.error) fail(`could not run ${command.join(' ')}: ${child.error.message}`)
  process.exit(child.status === null ? 1 : child.status)
}

// Run as a command rather than imported. Both sides are real paths: Node resolves a symlinked main module to
// its target, and `~/.claude/` is a tree of symlinks.
if (process.argv[1] && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url))) {
  await runHere(process.argv.slice(2))
}
