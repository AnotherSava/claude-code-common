// Cases for `claude/workflows/review-and-fix.js`, the saved workflow automated review loops run through.
//
// What it exists to guarantee is decided in plain code, not by an agent: which verified findings get code, that a
// round finding nothing worth code ends the loop, and that the loop never passes its cap. So the real script runs
// here under Node with the Workflow runtime's globals stubbed — `agent` answers from a scripted table keyed on the
// call's phase and round — and every case asserts on what the script decided and on the prompts it sent.

import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..')
const SOURCE = readFileSync(join(ROOT, 'claude', 'workflows', 'review-and-fix.js'), 'utf8')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const failures = []

function check(label, got, want) {
  const a = JSON.stringify(got), b = JSON.stringify(want)
  if (a !== b) failures.push(`  FAIL ${label}: got ${a}, want ${b}`)
}

// The runtime's own semantics, reduced: pipeline runs each item through its stages with no barrier and drops an item
// whose stage throws to null; parallel resolves a throwing thunk to null and never rejects.
async function pipeline(items, ...stages) {
  return Promise.all(items.map(async (item, index) => {
    try {
      let value = item
      for (const stage of stages) value = await stage(value, item, index)
      return value
    } catch { return null }
  }))
}
async function parallel(thunks) {
  return Promise.all(thunks.map(async thunk => { try { return await thunk() } catch { return null } }))
}

function finding(id, overrides = {}) {
  return { file: `src/${id}.ts`, summary: `defect ${id}`, failure_scenario: `scenario ${id}`, reached_by: 'none found', frequency: 'rare', cost_unhandled: 'cosmetic', ...overrides }
}
function verdict(real, reached, frequency, cost, overrides = {}) {
  return { real, reached, reached_by: reached ? 'call site' : 'none found', frequency, cost_unhandled: cost, duplicates_logic: false, reasoning: 'scripted', ...overrides }
}

// The ids a fix prompt lists, in the `- [r1-2] file: summary` shape the script writes them.
function promptIds(prompt) {
  return [...prompt.matchAll(/^- \[(r\d+-\d+)\]/gm)].map(m => m[1])
}

// `reviews[round]` is the findings list every lens returns that round; `verdicts[summary]` is the skeptic's answer, and
// a summary missing from it gets null, as a skipped or dead verifier does. The fixer applies every id it is given unless
// `fixer` says otherwise. `reviewer(lens, round)` and `verifier(summary, round)` override an answer when they return
// anything but undefined: return null, or throw, as the runtime can.
async function run(args, reviews, verdicts, { fixer, reviewer, verifier } = {}) {
  const calls = []
  async function agent(prompt, opts) {
    calls.push({ prompt, ...opts })
    const round = Number((opts.label.match(/:r(\d+)$/) || [])[1])
    if (opts.phase === 'Review') {
      const lens = opts.label.split(':')[1]
      if (reviewer) { const answer = reviewer(lens, round); if (answer !== undefined) return answer }
      return { findings: reviews[round] || [] }
    }
    if (opts.phase === 'Verify') {
      const summary = (prompt.match(/Finding: (.*)/) || [])[1]
      if (verifier) { const answer = verifier(summary, round); if (answer !== undefined) return answer }
      return verdicts[summary] || null
    }
    if (opts.phase === 'Fix') return fixer ? fixer(prompt, round) : { applied: promptIds(prompt).map(id => ({ id, change: 'done' })), skipped: [], gate_exit: 0, gate_tail: 'ok' }
    throw new Error(`unexpected phase ${opts.phase}`)
  }
  const logs = []
  const body = SOURCE.replace(/^export const meta/m, 'const meta')
  const script = new AsyncFunction('agent', 'pipeline', 'parallel', 'phase', 'log', 'args', body)
  const result = await script(agent, pipeline, parallel, () => {}, line => logs.push(line), args)
  return { result, calls, logs }
}

const LENSES = [{ key: 'bugs', prompt: 'find bugs' }]
const ARGS = { scope: 'the diff', lenses: LENSES, context: 'Repo: scratch.', gate: 'bash .claude/commit-checks.sh' }

async function triageAndStop() {
  const reviews = {
    1: [
      finding('common', { frequency: 'common', cost_unhandled: 'recoverable' }),
      finding('rare'),
      finding('unreached-severe', { cost_unhandled: 'data_loss' }),
      finding('false'),
      finding('theoretical-severe', { frequency: 'theoretical', cost_unhandled: 'crash' }),
      finding('theoretical-cosmetic', { frequency: 'theoretical' }),
      finding('rare-duplication'),
      finding('unreached-duplication'),
    ],
    2: [finding('common'), finding('round-two-rare')],
  }
  const verdicts = {
    'defect common': verdict(true, true, 'common', 'recoverable'),
    'defect rare': verdict(true, true, 'rare', 'cosmetic'),
    'defect unreached-severe': verdict(true, false, 'rare', 'data_loss'),
    'defect false': verdict(false, true, 'common', 'crash'),
    'defect theoretical-severe': verdict(true, true, 'theoretical', 'crash'),
    'defect theoretical-cosmetic': verdict(true, true, 'theoretical', 'cosmetic'),
    'defect rare-duplication': verdict(true, true, 'rare', 'cosmetic', { duplicates_logic: true }),
    // reached_by is overridden because the helper derives 'none found' from reached=false, and a fix-class item
    // carrying that string would make the 'verifier's evidence, not the reviewer's' check below pass vacuously.
    // It is also what a verifier marking a duplication would actually write: the copies are there to point at.
    'defect unreached-duplication': verdict(true, false, 'rare', 'cosmetic', { duplicates_logic: true, reached_by: 'both copies are in the source' }),
    'defect round-two-rare': verdict(true, true, 'rare', 'recoverable'),
  }
  const { result, calls } = await run(ARGS, reviews, verdicts)
  const disposition = Object.fromEntries(result.triage.map(r => [r.finding, r.disposition]))
  check('common and reached is fixed', disposition['defect common'], 'fix')
  check('rare and cosmetic gets a warning or doc line', disposition['defect rare'], 'warn_or_doc')
  check('no evidence anyone reaches it is dropped, however severe', disposition['defect unreached-severe'], 'drop')
  check('untrue is refuted', disposition['defect false'], 'refuted')
  check('reached with a severe cost is fixed even when theoretical', disposition['defect theoretical-severe'], 'fix')
  check('theoretical and cosmetic is dropped', disposition['defect theoretical-cosmetic'], 'drop')
  // Same ratings as 'defect rare' above, which warns: the flag is the only difference, so this pins the flag.
  check('a duplication is fixed on the same ratings that warn without it', disposition['defect rare-duplication'], 'fix')
  // Same ratings as 'defect unreached-severe' above, which drops. The copies are in the source whether or not their
  // divergence has fired yet, so the flag has to sit above the reached test and not merely above frequency.
  check('a duplication is fixed even where nothing reaches the divergence', disposition['defect unreached-duplication'], 'fix')
  check('a finding seen in round one is not verified again', result.triage.filter(r => r.finding === 'defect common').length, 1)
  check('round two with nothing fix-class stops the loop', result.stop_reason, 'round 2 found nothing that earns code')

  const fixes = calls.filter(c => c.phase === 'Fix')
  check('one fix call per round', fixes.length, 2)
  const first = fixes[0].prompt
  check('round one fix names the fix-class items', ['defect common', 'defect theoretical-severe'].every(s => first.includes(s)), true)
  check('round one fix carries no dropped or refuted item', ['defect unreached-severe', 'defect false', 'defect theoretical-cosmetic'].some(s => first.includes(s)), false)
  check('a warn item reaches the fixer as a log line or doc sentence only', first.includes('add only a log line or a sentence in the docs') && first.includes('defect rare'), true)
  check('round two fix is warn-only', fixes[1].prompt.includes('defect round-two-rare') && !fixes[1].prompt.includes('Fix these confirmed defects'), true)
  check('the fixer gets the verifier\'s evidence, not the reviewer\'s', first.includes('reached by: call site') && first.includes("verifier's reasoning: scripted") && !first.includes('reached by: none found'), true)
  check('the gate runs by exit status', first.includes('bash .claude/commit-checks.sh') && first.includes('exit status'), true)
  const roundTwoReviews = calls.filter(c => c.phase === 'Review' && c.label.endsWith(':r2'))
  check('round two reviewers are told what round one fixed', roundTwoReviews.every(c => c.prompt.includes('- [fix, applied] src/common.ts: defect common')), true)
  check('and what it warned on, dropped and refuted, so a rewording is not re-verified', roundTwoReviews.every(c => ['- [warn_or_doc, applied] src/rare.ts', '- [drop] src/unreached-severe.ts', '- [refuted] src/false.ts', '- [drop] src/theoretical-cosmetic.ts'].every(s => c.prompt.includes(s))), true)
  check('every fix- and warn-class row records that the fixer applied it', result.triage.filter(r => r.disposition === 'fix' || r.disposition === 'warn_or_doc').every(r => r.outcome === 'applied'), true)
  check('every agent prompt forbids launching an app', calls.every(c => c.prompt.includes('Never deploy, start, restart or stop any app')), true)
  check('every review and verify prompt is read-only', calls.filter(c => c.phase !== 'Fix').every(c => c.prompt.includes('You are read-only')), true)
}

async function stopsAfterQuietRound() {
  const { result, calls } = await run(ARGS, { 1: [finding('only-rare')] }, { 'defect only-rare': verdict(true, true, 'rare', 'cosmetic') })
  check('a first round with nothing fix-class stops there', result.stop_reason, 'round 1 found nothing that earns code')
  check('so the reviewers run once', calls.filter(c => c.phase === 'Review').length, LENSES.length)
}

async function nothingFoundCallsNoFixer() {
  const { result, calls } = await run(ARGS, { 1: [] }, {})
  check('no findings means no fix call', calls.filter(c => c.phase === 'Fix').length, 0)
  check('and an empty triage table', result.triage, [])
}

async function capsAtTwoRounds() {
  const always = n => [finding(`fix-${n}`, { frequency: 'common', cost_unhandled: 'crash' })]
  const verdicts = Object.fromEntries([1, 2, 3].map(n => [`defect fix-${n}`, verdict(true, true, 'common', 'crash')]))
  const { result, calls } = await run({ ...ARGS, lenses: [LENSES[0], { key: 'perf', prompt: 'find slow code' }] }, { 1: always(1), 2: always(2), 3: always(3) }, verdicts)
  check('the loop stops at the cap while fix-class findings keep coming', result.stop_reason, 'hard cap of 2 rounds reached')
  check('no third round of reviewers', calls.some(c => c.label.endsWith(':r3')), false)
}

async function noGate() {
  const { calls } = await run({ ...ARGS, gate: undefined }, { 1: [finding('g', { frequency: 'common' })] }, { 'defect g': verdict(true, true, 'common', 'recoverable') })
  check('without a gate the fixer is told to report it as not run', calls.find(c => c.phase === 'Fix').prompt.includes('No gate command was given'), true)
}

async function refusesBadArgs() {
  for (const [label, args] of [['no args', undefined], ['no scope', { lenses: LENSES }], ['no lenses', { scope: 'x', lenses: [] }], ['a lens without a prompt', { scope: 'x', lenses: [{ key: 'k' }] }]]) {
    let threw = false
    try { await run(args, {}, {}) } catch { threw = true }
    check(`refuses ${label}`, threw, true)
  }
}

const FIXABLE = finding('fixable', { frequency: 'common', cost_unhandled: 'crash' })
const FIXABLE_VERDICT = { 'defect fixable': verdict(true, true, 'common', 'crash') }

async function unverifiedIsNotRefuted() {
  const reviews = { 1: [FIXABLE, finding('dead-verifier', { cost_unhandled: 'data_loss' })], 2: [finding('dead-verifier', { cost_unhandled: 'data_loss' })] }
  const verifier = (summary, round) => summary === 'defect dead-verifier' ? (round === 1 ? null : verdict(true, true, 'rare', 'data_loss')) : undefined
  const { result, calls } = await run(ARGS, reviews, FIXABLE_VERDICT, { verifier })
  const rows = result.triage.filter(r => r.finding === 'defect dead-verifier')
  check('a finding whose verifier returned nothing is unverified, not refuted', rows[0].disposition, 'unverified')
  check('and its row says it was neither confirmed nor refuted', rows[0].why.includes('neither confirmed nor refuted'), true)
  check('and it does not reach the fixer', calls.find(c => c.phase === 'Fix').prompt.includes('defect dead-verifier'), false)
  check('round two reviewers are asked to report it again', calls.filter(c => c.phase === 'Review' && c.label.endsWith(':r2')).every(c => c.prompt.includes('never verified, so report them again if they still hold:\n- src/dead-verifier.ts: defect dead-verifier')), true)
  check('so a later round verifies it', rows.map(r => r.disposition), ['unverified', 'fix'])
}

async function verifierThatThrows() {
  const verifier = summary => { if (summary === 'defect thrown') throw new Error('budget spent') }
  const { result } = await run(ARGS, { 1: [finding('thrown', { frequency: 'common' })] }, {}, { verifier })
  check('a verifier that throws leaves the finding in the table as unverified', result.triage.map(r => r.disposition), ['unverified'])
  check('and the round says it went unverified rather than clean', result.stop_reason, 'round 1 found nothing that earns code among what ran; 1 finding(s) went unverified')
}

async function deadFixerStopsTheLoop() {
  for (const [label, fixer] of [['returns nothing', () => null], ['throws', () => { throw new Error('budget spent') }]]) {
    const { result, calls } = await run(ARGS, { 1: [FIXABLE], 2: [finding('later', { frequency: 'common' })] }, FIXABLE_VERDICT, { fixer })
    check(`a fixer that ${label} ends the loop`, result.stop_reason, `round 1's fixer returned nothing, so none of its fixes were applied`)
    check(`so no round two reviewer is told a fix was applied (fixer ${label})`, calls.some(c => c.label.endsWith(':r2')), false)
    check(`and the row says the fix was not applied (fixer ${label})`, result.triage[0].outcome, 'not applied: the fixer returned nothing')
  }
}

async function skippedFixIsNotReportedAsFixed() {
  const reviews = { 1: [FIXABLE, finding('declined', { frequency: 'common' })], 2: [] }
  const verdicts = { ...FIXABLE_VERDICT, 'defect declined': verdict(true, true, 'common', 'recoverable') }
  const fixer = () => ({ applied: [{ id: 'r1-1', change: 'done' }], skipped: [{ id: 'r1-2', why: 'already handled' }], gate_exit: 0, gate_tail: 'ok' })
  const { result, calls } = await run(ARGS, reviews, verdicts, { fixer })
  const review = calls.find(c => c.phase === 'Review' && c.label.endsWith(':r2')).prompt
  check('round two is told the applied fix was applied', review.includes('- [fix, applied] src/fixable.ts'), true)
  check('and the skipped one was skipped, with the reason', review.includes('- [fix, skipped: already handled] src/declined.ts'), true)
  check('the skipped row carries the outcome', result.triage.find(r => r.finding === 'defect declined').outcome, 'skipped: already handled')

  const none = await run(ARGS, reviews, verdicts, { fixer: () => ({ applied: [], skipped: [{ id: 'r1-1', why: 'x' }], gate_exit: 0, gate_tail: 'ok' }) })
  check('a fixer that applies nothing ends the loop', none.result.stop_reason, `round 1's fixer applied none of its fixes`)
  check('and an item it neither applied nor skipped says so', none.result.triage.find(r => r.finding === 'defect declined').outcome, 'not applied: the fixer did not report it')
}

async function silentLensIsReported() {
  const lenses = [{ key: 'a', prompt: 'x' }, { key: 'b', prompt: 'y' }]
  for (const [label, answer] of [['returns nothing', () => null], ['throws', () => { throw new Error('budget spent') }]]) {
    const reviewer = lens => lens === 'b' ? answer() : undefined
    const { result, logs } = await run({ ...ARGS, lenses }, { 1: [finding('only-rare')] }, { 'defect only-rare': verdict(true, true, 'rare', 'cosmetic') }, { reviewer })
    check(`a lens whose reviewer ${label} is listed`, result.silent_lenses, [{ round: 1, lens: 'b' }])
    check(`and the round does not call itself clean (reviewer ${label})`, result.stop_reason, 'round 1 found nothing that earns code among what ran; the b lens returned nothing')
    check(`and the log names it (reviewer ${label})`, logs.some(l => l.includes('the b reviewer returned nothing')), true)
  }
}

// The Workflow tool refuses a script holding a carriage return, and it reads the working copy through
// ~/.claude/workflows, so a CRLF file breaks every run while git, normalizing to LF, shows nothing changed.
check('the workflow file carries no carriage return', SOURCE.includes('\r'), false)

for (const test of [triageAndStop, stopsAfterQuietRound, nothingFoundCallsNoFixer, capsAtTwoRounds, noGate, refusesBadArgs, unverifiedIsNotRefuted, verifierThatThrows, deadFixerStopsTheLoop, skippedFixIsNotReportedAsFixed, silentLensIsReported]) {
  try { await test() } catch (error) { failures.push(`  FAIL ${test.name} threw: ${error.stack}`) }
}
for (const line of failures) console.log(line)
console.log(`review-and-fix tests: ${failures.length ? `${failures.length} failure(s)` : 'all cases behave'}`)
process.exit(failures.length ? 1 : 0)
