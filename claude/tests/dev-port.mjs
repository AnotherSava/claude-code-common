// Cases for `claude/skills/ports/scripts/dev-port.mjs`, the shim every registry-resolved dev server starts
// through. Nothing else in this gate executes that file — `claude/tests/ports.py` only writes its name into
// fixtures — so the code that launches those servers was the one unexercised piece of the ports skill while
// the checker reading the registry was covered twice.
//
// A regression here starts the server on a port nothing allocated, or not at all, in every repo that has
// adopted convention 015, and says so in a message about a missing file or a framework default rather than
// about a port. The case that paid for the file is Windows argument delivery: under `shell: true` Node
// concatenates an argv array with no escaping, so cmd.exe re-splits each argument at its spaces and a
// checkout under `C:\Users\First Last\` cannot start — measured on Windows 11 with Node v24.19.0, where the
// array form failed with `'C:\Users\Public\ccd' is not recognized` and one pre-quoted line delivered every
// argument whole.
//
// Both branches run for real, against the real `ports.py` under a scratch registry so no claim is written.
// `run()` picks its branch from `process.platform`, so each case spawns a driver that forces that value
// before importing the module — which also flips the interpreter name `resolvePort` asks for, hence the
// `python` stand-in on a POSIX host. The branch a host cannot drive is reported NOT COVERED, in the summary
// line as well, since a case that never ran must not read as one that passed.
//
// Usage:  node claude/tests/dev-port.mjs
// Exit:   0 every case that ran behaves, 1 one does not

import { spawnSync } from 'node:child_process'
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..')
const MODULE = join(ROOT, 'claude', 'skills', 'ports', 'scripts', 'dev-port.mjs')
const WINDOWS = process.platform === 'win32'

// The platform each branch needs. On Windows the native value already selects the shell branch, and the
// argv branch has to be forced — which makes `resolvePort` ask for `python3` there.
const SHELL_BRANCH = WINDOWS ? 'native' : 'win32'
const ARGV_BRANCH = WINDOWS ? 'linux' : 'native'

// Node reads `comspec` for the shell it spawns under `shell: true`. A POSIX host has no cmd.exe, so the
// line `windowsCommandLine` builds is handed to /bin/sh, which applies the same double-quote rule to it.
const SHELL_ENV = WINDOWS ? {} : { comspec: '/bin/sh' }

const DRIVER = `import { pathToFileURL } from 'node:url'

const [modulePath, platform, ...command] = process.argv.slice(2)
if (platform !== 'native') Object.defineProperty(process, 'platform', { value: platform })
const { run } = await import(pathToFileURL(modulePath).href)
await run({ useCase: 'dev-port-selftest', owner: 'claude-tests', command })
`

const ECHO = `console.log('PORT=' + (process.env.PORT ?? ''))
for (const arg of process.argv.slice(2)) console.log('arg=[' + arg + ']')
`

const PYTHON_SHIM = '#!/bin/sh\nexec python3 "$@"\n'

const failures = []
const uncovered = []
const passed = []

function check(label, got, want) {
  const a = JSON.stringify(got), b = JSON.stringify(want)
  if (a === b) return
  failures.push(`  FAIL ${label}: got ${a}, want ${b}`)
}

// The scratch root and the directory under it both carry a space on purpose: the command's own path, the
// script path inside it and a `--config` argument all have to survive whichever parser the branch uses.
const scratch = mkdtempSync(join(tmpdir(), 'dev-port test.'))
const probe = join(scratch, 'probe dir')
mkdirSync(probe)
const driver = join(scratch, 'driver.mjs')
const echo = join(probe, 'echo-args.mjs')
const config = join(probe, 'cfg.json')
const registry = join(scratch, 'registry.json')
writeFileSync(driver, DRIVER)
writeFileSync(echo, ECHO)
writeFileSync(config, '{}')
writeFileSync(registry, JSON.stringify({ claims: [] }))

const env = { ...process.env, CLAUDE_PORTS_REGISTRY: registry }
if (!WINDOWS) {
  const bin = join(scratch, 'bin')
  mkdirSync(bin)
  const python = join(bin, 'python')
  writeFileSync(python, PYTHON_SHIM)
  chmodSync(python, 0o755)
  env.PATH = `${bin}:${env.PATH}`
}

function execute(platform, extraArgs, extraEnv) {
  const command = [process.execPath, echo, 'dev', '--config', config, ...extraArgs]
  const result = spawnSync(process.execPath, [driver, MODULE, platform, ...command],
                           { encoding: 'utf-8', env: { ...env, ...extraEnv } })
  const strip = (text) => (text || '').replace(/\r/g, '')
  return { status: result.status, out: strip(result.stdout), err: strip(result.stderr), error: result.error }
}

const delivered = (out) => [...out.matchAll(/^arg=\[(.*)\]$/gm)].map((m) => m[1])
const reportedPort = (out) => (out.match(/^PORT=(\d*)$/m) || [])[1]

function allocatedPort() {
  const claims = JSON.parse(readFileSync(registry, 'utf8')).claims || []
  return claims.find((claim) => claim.use_case === 'dev-port-selftest')?.port
}

// The command's own path holds a space, so a branch that re-splits it leaves Node unable to find the script
// and the exit status carries the failure before any assertion on the arguments does.
function deliversEveryArgument(label, platform, extraEnv) {
  const run = execute(platform, [], extraEnv)
  if (run.status !== 0) failures.push(`  FAIL ${label}: exited ${run.status}, and its last words were:\n${run.err.trimEnd().split('\n').slice(-6).join('\n')}`)
  check(`${label}: delivers every argument whole`, delivered(run.out), ['dev', '--config', config])
  check(`${label}: exports the port the registry assigned`, reportedPort(run.out), String(allocatedPort() ?? ''))
  passed.push(label)
  return run
}

function shellBranchCases() {
  const run = deliversEveryArgument('the shell branch', SHELL_BRANCH, SHELL_ENV)
  // A regression to `spawnSync(cmd, args, { shell: true })` would deliver these arguments split AND warn;
  // the warning is the cheaper signal of the two, and it names the mechanism.
  check('the shell branch: emits no DEP0190', run.err.includes('DEP0190'), false)

  const meta = execute(SHELL_BRANCH, ['--title=a&b'], SHELL_ENV)
  check('a cmd.exe metacharacter arrives as one token', delivered(meta.out).at(-1), '--title=a&b')
  passed.push('a metacharacter token')

  const quoted = execute(SHELL_BRANCH, ['say "hi"'], SHELL_ENV)
  check('an embedded double quote is refused, not mangled', quoted.status, 1)
  check('and the refusal names the argument', quoted.err.includes('say \\"hi\\"'), true)
  check('and the command never runs', delivered(quoted.out), [])
  passed.push('the embedded-quote refusal')
}

function argvBranchCases() {
  deliversEveryArgument('the argv branch', ARGV_BRANCH, {})

  // The refusal belongs to the shell branch alone: with no shell in the way a quote needs no escaping, and
  // refusing one here would reject an argument the platform can carry.
  const quoted = execute(ARGV_BRANCH, ['say "hi"'], {})
  check('the argv branch carries an embedded quote rather than refusing it', [quoted.status, delivered(quoted.out).at(-1)], [0, 'say "hi"'])
  passed.push('an embedded quote on the argv branch')
}

// `resolvePort` fails before it needs an interpreter or a branch, so these cases run natively on either
// host. They redirect both home variables because `os.homedir()` reads a different one per platform and the
// forced platform has no say in which — `absence-versus-unreadable.md` measures that.
function registryStateCases() {
  const home = join(scratch, 'scratch home')
  const scripts = join(home, '.claude', 'skills', 'ports', 'scripts')
  mkdirSync(scripts, { recursive: true })
  const homeEnv = { HOME: home, USERPROFILE: home }

  const absent = execute('native', [], homeEnv)
  check('a missing registry script reports an install',
        [absent.status, /is not installed on this machine/.test(absent.err)], [1, true])
  passed.push('the absent registry script')

  // The state that motivates the predicate: `~/.claude/` is symlinked out of the dotfiles checkout, so
  // moving that checkout leaves exactly this, and `existsSync` cannot tell it from the case above.
  try {
    symlinkSync(join(scratch, 'no such tree', 'ports.py'), join(scripts, 'ports.py'))
  } catch (error) {
    uncovered.push(`the dangling-symlink state: this host refused to create the link (${error.code})`)
    return
  }
  const dangling = execute('native', [], homeEnv)
  check('a dangling symlink reports a repair, naming the link',
        [dangling.status, /symlink resolving to nothing/.test(dangling.err), /is not installed/.test(dangling.err)],
        [1, true, false])
  passed.push('the dangling-symlink state')
}

try {
  registryStateCases()
  shellBranchCases()

  // Forcing the argv branch on Windows makes `resolvePort` ask for `python3`, and a `.cmd` stand-in cannot
  // substitute: Node refuses to spawn one without a shell. Where it is absent the branch goes unmeasured —
  // it is also not the branch Windows runs, so nothing production depends on is left unasserted.
  const argvInterpreter = WINDOWS ? 'python3' : null
  if (argvInterpreter && spawnSync(argvInterpreter, ['--version'], { encoding: 'utf-8' }).status !== 0) {
    uncovered.push(`the argv branch: driving it here needs \`${argvInterpreter}\` on PATH, which is absent`)
  } else {
    argvBranchCases()
  }
} catch (error) {
  failures.push(`  FAIL the run could not be set up: ${error.stack}`)
} finally {
  rmSync(scratch, { recursive: true, force: true })
}

for (const line of failures) console.log(line)
for (const line of uncovered) console.log(`  NOT COVERED ${line}`)
const tally = `${passed.length} case(s) behave`
const missing = uncovered.length ? `, ${uncovered.length} NOT COVERED — ${uncovered[0]}` : ''
console.log(`dev-port tests: ${failures.length ? `${failures.length} failure(s)` : tally}${missing}`)
process.exit(failures.length ? 1 : 0)
