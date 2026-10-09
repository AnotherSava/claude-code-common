export const meta = {
  name: 'review-and-fix',
  description: 'Review a change through given lenses, verify each finding for truth and realism, triage in code, and fix only what earns code',
  whenToUse: 'Any automated review loop that fixes what it finds. args: {scope, lenses: [{key, prompt}], context, gate}. Returns the full triage table for the user, never just "all fixed".',
  phases: [
    { title: 'Review', detail: 'one reviewer per lens; every finding names who reaches it, how often, and what it costs' },
    { title: 'Verify', detail: 'one skeptic per finding, judging truth and realism' },
    { title: 'Fix', detail: 'one agent applies the fix-class findings, adds a log line or doc sentence for warn-class, runs the gate' },
  ],
}

// Why this exists: a review-and-fix loop that verifies and fixes on its own never shows its findings to anyone, so
// `feedback_realism_before_hardening` never fires. Measured in tauri-dashboard on 2026-10-02: 10 review rounds
// confirmed 125 findings, 85 of them rated low, and every one was coded. Here realism is a field every finding must
// carry, the skeptic judges it, plain code decides what gets code, and the loop stops when a round finds nothing
// worth fixing.

const MAX_ROUNDS = 2
const SEVERE = ['data_loss', 'crash', 'wrong_core_output', 'identity_leak']
const FREQUENCIES = ['common', 'plausible', 'rare', 'theoretical']
const COSTS = [...SEVERE, 'recoverable', 'cosmetic']

// What duplicates_logic means, held once. The verdict schema's field description and the verifier's step 3 both
// define this flag for the same reader, so two wordings of it would tell that reader two different things — which is
// the class `triage` below routes to a fix rather than to a log line.
const DUPLICATION = 'one computation or step-sequence exists in more than one place, so what it costs is the next divergence between the copies rather than anything the rated scenario does'

const HANDS_OFF = 'Never deploy, start, restart or stop any app, and never open a window. Run no command that launches one.'
const READ_ONLY = 'You are read-only: do not edit, create or delete any file in the repo. Scratch files go only in a fresh temp directory, which you remove afterwards.'

const FINDINGS = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file: { type: 'string' },
          summary: { type: 'string', description: 'one sentence: what the code does wrong' },
          failure_scenario: { type: 'string', description: 'concrete inputs or state, and the wrong outcome they produce' },
          reached_by: { type: 'string', description: 'the concrete writer, caller or user action that puts the code in this state, with evidence: a call site, a log line, a stored record. "none found" when you have none.' },
          frequency: { type: 'string', enum: FREQUENCIES },
          cost_unhandled: { type: 'string', enum: COSTS },
        },
        required: ['file', 'summary', 'failure_scenario', 'reached_by', 'frequency', 'cost_unhandled'],
      },
    },
  },
  required: ['findings'],
}

const VERDICT = {
  type: 'object',
  properties: {
    real: { type: 'boolean', description: 'the code does mishandle the scenario as described' },
    reached: { type: 'boolean', description: 'you found evidence that something actually puts the code in this state' },
    reached_by: { type: 'string', description: 'that evidence, or why there is none' },
    frequency: { type: 'string', enum: FREQUENCIES },
    cost_unhandled: { type: 'string', enum: COSTS },
    duplicates_logic: { type: 'boolean', description: `the finding is that ${DUPLICATION}` },
    reasoning: { type: 'string' },
  },
  required: ['real', 'reached', 'reached_by', 'frequency', 'cost_unhandled', 'duplicates_logic', 'reasoning'],
}

const FIX_REPORT = {
  type: 'object',
  properties: {
    applied: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, change: { type: 'string' } }, required: ['id', 'change'] } },
    skipped: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, why: { type: 'string' } }, required: ['id', 'why'] } },
    gate_exit: { type: ['integer', 'null'], description: 'the gate command\'s exit status, or null when no gate was given' },
    gate_tail: { type: 'string', description: 'the last lines of the gate output' },
  },
  required: ['applied', 'skipped', 'gate_exit', 'gate_tail'],
}

// The skeptic's ratings decide, not the reviewer's: the reviewer found the case and is the one inclined to rate it up.
// No verdict at all is its own outcome: a finding nobody verified is neither confirmed nor disproved.
function triage(verdict) {
  if (!verdict) return 'unverified'
  if (!verdict.real) return 'refuted'
  // Above the `reached` test, and above frequency, because both describe the scenario while a duplication's cost sits
  // outside it: the next divergence between the copies, on whatever schedule they are edited. The copies are readable
  // in the source, so `reached` has nothing to add — and asking a verifier for evidence that the divergence already
  // fires invites the exact judgement ~/.claude/memory/feedback_realism_before_hardening.md records on 2026-10-09,
  // where a divergence measured unreachable on every project here was used to argue for parking the consolidation.
  // `real` still gates it: a finding claimed as a duplication that is not one must not reach the fixer.
  if (verdict.duplicates_logic) return 'fix'
  if (!verdict.reached) return 'drop'
  if (SEVERE.includes(verdict.cost_unhandled)) return 'fix'
  if (verdict.frequency === 'common' || verdict.frequency === 'plausible') return 'fix'
  if (verdict.frequency === 'rare') return 'warn_or_doc'
  return 'drop'
}

function requireArgs() {
  if (!args || typeof args !== 'object') throw new Error('review-and-fix needs args: {scope, lenses: [{key, prompt}], context, gate}')
  if (typeof args.scope !== 'string' || !args.scope.trim()) throw new Error('review-and-fix: args.scope must name what to review, e.g. "the uncommitted diff in <repo>"')
  if (!Array.isArray(args.lenses) || !args.lenses.length || args.lenses.some(l => !l || typeof l.key !== 'string' || typeof l.prompt !== 'string')) throw new Error('review-and-fix: args.lenses must be a non-empty array of {key, prompt}')
}

requireArgs()
const CONTEXT = typeof args.context === 'string' ? args.context : ''
const GATE = typeof args.gate === 'string' && args.gate.trim() ? args.gate.trim() : null

// agent() returns null when the user skips a call or the subagent dies after its retries, and throws once a budget is
// spent. Both become null here, with a log line naming the call, so a throw cannot reject the run and lose the table.
async function call(prompt, opts) {
  try {
    return await agent(prompt, opts)
  } catch (error) {
    log(`${opts.label} threw: ${error?.message || error}`)
    return null
  }
}

// Later rounds see every earlier finding with its outcome, not only the fixes: a reviewer told only what was fixed
// re-finds the dropped and rare cases in new words, and a fresh skeptic can rate them up into code.
function reviewPrompt(lens, round, earlier) {
  const line = r => `- [${r.outcome ? `${r.disposition}, ${r.outcome}` : r.disposition}] ${r.file}: ${r.summary}`
  const settled = earlier.filter(r => r.disposition !== 'unverified')
  const unverified = earlier.filter(r => r.disposition === 'unverified')
  const later = round > 1
    ? `\n\nRound ${round}. Earlier rounds already triaged the findings below, and the scope now also includes the code their applied fixes added. Do not re-report any of them in any wording, including the dropped and refuted ones; a finding is new only if it lies in code a fix added or is absent from this list:\n${settled.map(line).join('\n')}${unverified.length ? `\nThese were never verified, so report them again if they still hold:\n${unverified.map(r => `- ${r.file}: ${r.summary}`).join('\n')}` : ''}`
    : ''
  return `${CONTEXT}\n\nScope: ${args.scope}\n\nLens (${lens.key}): ${lens.prompt}${later}\n\n${READ_ONLY} ${HANDS_OFF}\n\nReport only concrete defects. For each one say who reaches it: the writer, caller or user action that puts the code in that state, with evidence (a call site, a log line, a stored record). A case you can construct but cannot show anyone reaching gets reached_by "none found" and frequency "theoretical" — report it that way rather than leaving it out, so the triage can see it. Rate frequency (common, plausible, rare, theoretical) and the cost of leaving it unhandled (data_loss, crash, wrong_core_output, identity_leak, recoverable, cosmetic). No style nits.`
}

function verifyPrompt(finding, lens) {
  return `${CONTEXT}\n\nScope: ${args.scope}\n\n${READ_ONLY} ${HANDS_OFF}\n\nAdversarially verify this finding from the ${lens.key} lens. Judge two things separately.\n1. Truth: does the code mishandle the scenario as described? Reproduce it in scratch space or show why it cannot happen, is already handled, or is a deliberate documented limit. real=false if you cannot demonstrate it.\n2. Realism: find the evidence that something actually puts the code in this state — a call site that passes that input, a log line, a stored record, a user report. A reviewer confirming the code mishandles a case is not evidence that anyone is in it. reached=false when you find none. Then give your own frequency and cost ratings; do not copy the reviewer's.\n3. Duplication: set duplicates_logic true when the defect is that ${DUPLICATION}. Your frequency and cost ratings then describe the wrong thing, so give them as you see them and let the flag carry the rest.\n\nFinding: ${finding.summary}\nFile: ${finding.file}\nScenario: ${finding.failure_scenario}\nReviewer's reached_by: ${finding.reached_by}\nReviewer's ratings: ${finding.frequency}, ${finding.cost_unhandled}`
}

// Each item carries the skeptic's evidence rather than the reviewer's: the reviewer may have had none for a case the
// skeptic showed reached, and the skeptic's reasoning names the case it confirmed, which can be narrower. A round with
// only warn-class items sends no fix instruction at all, so the rare cases cannot be read as defects to code.
function fixPrompt(fixes, warns) {
  const list = items => items.map(r => `- [${r.id}] ${r.file}: ${r.summary}\n  scenario: ${r.failure_scenario}\n  reached by: ${r.verdict.reached_by}\n  verifier's reasoning: ${r.verdict.reasoning}`).join('\n')
  const sections = [
    ...(fixes.length ? [`Fix these confirmed defects. Each was verified true and shown to be reached; where the verifier's reasoning confirms a narrower case than the scenario, fix the case it confirmed. An item the verifier marked duplicates_logic is fixed by making one definition every site calls, never by patching the copies in place, since patching each one ships the duplication intact:\n${list(fixes)}`] : []),
    ...(warns.length ? [`For each of these rare cases, add only a log line or a sentence in the docs that names the case. Add no logic, no branch, no guard and no test for them:\n${list(warns)}`] : []),
  ]
  const gate = GATE
    ? `When done, run the project's gate exactly as \`${GATE}\` with its output redirected to a file and no pipe after it, and report its exit status as gate_exit. A pipe would replace the gate's exit status with the last command's. Do not trim or filter what you read to decide pass or fail.`
    : 'No gate command was given: report gate_exit null and say so in gate_tail.'
  return `${CONTEXT}\n\nScope: ${args.scope}\n\n${HANDS_OFF}\n\n${sections.join('\n\n')}\n\nTouch nothing beyond what these items need. If an item turns out not to need a change, skip it and say why. ${gate}`
}

// Each fix- and warn-class row records what the fixer did with it, read from its report rather than assumed.
async function fixRound(round, fixes, warns) {
  const report = await call(fixPrompt(fixes, warns), { label: `fix:r${round}`, phase: 'Fix', schema: FIX_REPORT })
  fixReports.push({ round, report })
  const applied = new Set((report?.applied || []).map(a => a.id))
  const skipped = new Map((report?.skipped || []).map(s => [s.id, s.why]))
  for (const r of [...fixes, ...warns]) {
    r.outcome = !report ? 'not applied: the fixer returned nothing'
      : applied.has(r.id) ? 'applied'
      : skipped.has(r.id) ? `skipped: ${skipped.get(r.id)}`
      : 'not applied: the fixer did not report it'
  }
  return report
}

const table = []
const fixReports = []
const silentLenses = []
const seen = new Set()
let stopReason = `hard cap of ${MAX_ROUNDS} rounds reached`

for (let round = 1; round <= MAX_ROUNDS; round++) {
  const silent = []
  const rows = (await pipeline(
    args.lenses,
    lens => call(reviewPrompt(lens, round, table), { label: `review:${lens.key}:r${round}`, phase: 'Review', schema: FINDINGS }),
    (review, lens) => {
      if (!review) {
        silent.push(lens.key)
        log(`round ${round}: the ${lens.key} reviewer returned nothing, so that lens went unreviewed`)
        return []
      }
      return parallel((review.findings || [])
        .map(f => ({ f, key: `${f.file}::${f.summary}` }))
        .filter(({ key }) => { if (seen.has(key)) return false; seen.add(key); return true })
        .map(({ f, key }) => () => call(verifyPrompt(f, lens), { label: `verify:${lens.key}:r${round}`, phase: 'Verify', schema: VERDICT })
          .then(v => {
            if (!v) seen.delete(key)
            return { ...f, lens: lens.key, round, verdict: v, disposition: triage(v) }
          })))
    },
  )).flat().filter(Boolean)

  silentLenses.push(...silent.map(lens => ({ round, lens })))
  rows.forEach((r, i) => { r.id = `r${round}-${i + 1}` })
  table.push(...rows)
  const fixes = rows.filter(r => r.disposition === 'fix')
  const warns = rows.filter(r => r.disposition === 'warn_or_doc')
  const unverified = rows.filter(r => r.disposition === 'unverified')
  log(`round ${round}: ${rows.length} found, ${fixes.length} fix, ${warns.length} warn_or_doc, ${rows.filter(r => r.disposition === 'drop').length} drop, ${rows.filter(r => r.disposition === 'refuted').length} refuted, ${unverified.length} unverified`)

  if (!fixes.length) {
    if (warns.length) await fixRound(round, [], warns)
    const gaps = [
      ...(silent.length ? [`the ${silent.join(', ')} lens returned nothing`] : []),
      ...(unverified.length ? [`${unverified.length} finding(s) went unverified`] : []),
    ]
    stopReason = `round ${round} found nothing that earns code${gaps.length ? ` among what ran; ${gaps.join(' and ')}` : ''}`
    break
  }
  const report = await fixRound(round, fixes, warns)
  if (!report) {
    stopReason = `round ${round}'s fixer returned nothing, so none of its fixes were applied`
    break
  }
  if (!fixes.some(r => r.outcome === 'applied')) {
    stopReason = `round ${round}'s fixer applied none of its fixes`
    break
  }
}

return {
  stop_reason: stopReason,
  note: 'Present the triage table to the user as a triage, not as "all fixed". Rare and theoretical items are reported with their ratings; another round is not offered by default. An unverified finding is neither confirmed nor disproved, and a lens in silent_lenses was never reviewed: say so rather than counting either as clean.',
  silent_lenses: silentLenses,
  triage: table.map(r => ({
    id: r.id,
    round: r.round,
    lens: r.lens,
    file: r.file,
    finding: r.summary,
    reached_by: r.verdict?.reached_by ?? r.reached_by,
    frequency: r.verdict?.frequency ?? r.frequency,
    cost: r.verdict?.cost_unhandled ?? r.cost_unhandled,
    disposition: r.disposition,
    outcome: r.outcome ?? null,
    why: r.verdict?.reasoning ?? 'the verifier returned nothing, so this finding is neither confirmed nor refuted',
  })),
  fixes: fixReports,
}
