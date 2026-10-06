#!/usr/bin/env node
// Runs this project's server on the port the ports registry holds for it.
//
// The number is deliberately not in this repo. It lives in one place — the registry at
// ~/.claude/skills/ports/ — so that two projects cannot quietly claim the same port, and a literal in a
// file that decides where a server listens is a defect rather than a second opinion. Prose is not: a
// README naming a URL, an `.env.example` default and a test asserting one are literals no launch-time
// resolution can replace, and the `ports-from-registry` rule does not look at them.
//
// Usage, from a package.json script:  node ../scripts/dev.mjs next dev
//
// The two constants below are this repo's. Everything else lives in the shared implementation, so a fix
// there reaches every project at once.

import { homedir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const USE_CASE = '{{use-case-slug}}'   // the registry's key for this server — `ports.py list` shows it
const OWNER = '{{repo-name}}'

const shared = join(homedir(), '.claude', 'skills', 'ports', 'scripts', 'dev-port.mjs')

let run
try {
  ;({ run } = await import(pathToFileURL(shared).href))
} catch (error) {
  console.error(
    `dev.mjs: could not load ${shared} (${error.message}).\n` +
    `This project's port comes from the claude dotfiles' ports registry, which is not installed on this ` +
    `machine. Install the dotfiles, or look the port up in that registry and run the server yourself with ` +
    `PORT=<n> set.`,
  )
  process.exit(1)
}

await run({ useCase: USE_CASE, owner: OWNER, command: process.argv.slice(2) })
