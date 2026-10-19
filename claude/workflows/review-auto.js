export const meta = {
  name: 'review-auto',
  description: 'Review a change through given lenses, verify each finding for truth and realism, triage in code, and fix only what earns code',
  whenToUse: 'Any automated review loop, fixing what it finds or, with fix: false, read-only. args: {scope, lenses: [{key, prompt}], context, gate, fix, rounds}. rounds caps the review-and-fix rounds, 2 when absent. In fix mode a converged run then polishes the change with /clean-code and /docs-relevance, reviews the polish, and reverts it whole if anything fails, so /commit has no code or prose left to polish (screenshot-relevance still runs there); a polish pass that returns nothing is the exception, left unreverted in the tree and unrecorded, since what it edited is unknown. Returns the full triage table for the user, never just "all fixed".',
  phases: [
    { title: 'Review', detail: 'one reviewer per lens; every finding names who reaches it, how often, and what it costs' },
    { title: 'Verify', detail: 'one skeptic per finding, judging truth and realism' },
    { title: 'Fix', detail: 'one agent applies the fix-class findings, adds a log line or doc sentence for warn-class, runs the gate' },
    { title: 'Polish', detail: 'once the review converged with no gap: /clean-code, then /docs-relevance over the polished code, then the gate' },
    { title: 'Polish review', detail: 'every lens over the polish diff alone; a confirmed defect or a gap reverts the whole polish' },
    { title: 'Bookmark', detail: 'one agent records which tree the review covered, when it covered all of it' },
  ],
}

// Why this exists: a review-and-fix loop that verifies and fixes on its own never shows its findings to anyone, so
// `feedback_realism_before_hardening` never fires. Measured in tauri-dashboard on 2026-10-02: 10 review rounds
// confirmed 125 findings, 85 of them rated low, and every one was coded. Here realism is a field every finding must
// carry, the skeptic judges it, plain code decides what gets code, and the loop stops when a round finds nothing
// worth fixing.

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

const COMMAND_REPORT = {
  type: 'object',
  properties: { exit_status: { type: 'integer' }, output: { type: 'string' } },
  required: ['exit_status', 'output'],
}

const POLISH_REPORT = {
  type: 'object',
  properties: {
    changes: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, change: { type: 'string' } }, required: ['file', 'change'] } },
    notes: { type: 'string', description: 'what the skill would have asked the user or suggested without doing, or empty' },
  },
  required: ['changes', 'notes'],
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
  if (!args || typeof args !== 'object') throw new Error('review-auto needs args: {scope, lenses: [{key, prompt}], context, gate, fix, rounds}')
  if (typeof args.scope !== 'string' || !args.scope.trim()) throw new Error('review-auto: args.scope must name what to review, e.g. "the uncommitted diff in <repo>"')
  if (!Array.isArray(args.lenses) || !args.lenses.length || args.lenses.some(l => !l || typeof l.key !== 'string' || typeof l.prompt !== 'string')) throw new Error('review-auto: args.lenses must be a non-empty array of {key, prompt}')
  if ('fix' in args && typeof args.fix !== 'boolean') throw new Error('review-auto: args.fix must be true or false')
  if ('rounds' in args && !(Number.isInteger(args.rounds) && args.rounds >= 1)) throw new Error('review-auto: args.rounds must be a whole number of at least 1')
}

requireArgs()
const CONTEXT = typeof args.context === 'string' ? args.context : ''
const GATE = typeof args.gate === 'string' && args.gate.trim() ? args.gate.trim() : null
// Read-only collects one round of findings and changes nothing (~/.claude/memory/feedback_read_only_review_loop.md). One
// round, because a later round exists to review the code an earlier round's fixes added, and here there is none.
const FIX = args.fix !== false
// A cap rather than a target: the loop stops sooner when a round finds nothing worth fixing. Read-only runs one round
// whatever this says, for the reason given above `FIX`.
const MAX_ROUNDS = args.rounds ?? 2
// Set by the review-scope hook (claude/hooks/review-scope.py), never by the caller: the repo, the commit the scope runs
// from, and the tree at launch. Absent when the hook could not trust a base, and then nothing is recorded.
const BOOKMARK = args.review_bookmark && typeof args.review_bookmark === 'object' && ['repo', 'base', 'tree'].every(k => typeof args.review_bookmark[k] === 'string') ? args.review_bookmark : null

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
function reviewPrompt(lens, round, earlier, scope) {
  const line = r => `- [${r.outcome ? `${r.disposition}, ${r.outcome}` : r.disposition}] ${r.file}: ${r.summary}`
  const settled = earlier.filter(r => r.disposition !== 'unverified')
  const unverified = earlier.filter(r => r.disposition === 'unverified')
  const later = round > 1
    ? `\n\nRound ${round}. Earlier rounds already triaged the findings below, and the scope now also includes the code their applied fixes added. Do not re-report any of them in any wording, including the dropped and refuted ones; a finding is new only if it lies in code a fix added or is absent from this list:\n${settled.map(line).join('\n')}${unverified.length ? `\nThese were never verified, so report them again if they still hold:\n${unverified.map(r => `- ${r.file}: ${r.summary}`).join('\n')}` : ''}`
    : ''
  return `${CONTEXT}\n\nScope: ${scope}\n\nLens (${lens.key}): ${lens.prompt}${later}\n\n${READ_ONLY} ${HANDS_OFF}\n\nReport only concrete defects. For each one say who reaches it: the writer, caller or user action that puts the code in that state, with evidence (a call site, a log line, a stored record). A case you can construct but cannot show anyone reaching gets reached_by "none found" and frequency "theoretical" — report it that way rather than leaving it out, so the triage can see it. Rate frequency (common, plausible, rare, theoretical) and the cost of leaving it unhandled (data_loss, crash, wrong_core_output, identity_leak, recoverable, cosmetic). No style nits.`
}

function verifyPrompt(finding, lens, scope) {
  return `${CONTEXT}\n\nScope: ${scope}\n\n${READ_ONLY} ${HANDS_OFF}\n\nAdversarially verify this finding from the ${lens.key} lens. Judge two things separately.\n1. Truth: does the code mishandle the scenario as described? Reproduce it in scratch space or show why it cannot happen, is already handled, or is a deliberate documented limit. real=false if you cannot demonstrate it.\n2. Realism: find the evidence that something actually puts the code in this state — a call site that passes that input, a log line, a stored record, a user report. A reviewer confirming the code mishandles a case is not evidence that anyone is in it. reached=false when you find none. Then give your own frequency and cost ratings; do not copy the reviewer's.\n3. Duplication: set duplicates_logic true when the defect is that ${DUPLICATION}. Your frequency and cost ratings then describe the wrong thing, so give them as you see them and let the flag carry the rest.\n\nFinding: ${finding.summary}\nFile: ${finding.file}\nScenario: ${finding.failure_scenario}\nReviewer's reached_by: ${finding.reached_by}\nReviewer's ratings: ${finding.frequency}, ${finding.cost_unhandled}`
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
let quiet = false

// One reviewer per lens, one skeptic per new finding. `tag` names the round in labels and ids; the polish review passes
// its own `seen`, so a finding worded like an earlier round's is still verified against the polish diff.
async function reviewRound({ round, tag, scope, earlier, seen, reviewPhase, verifyPhase }) {
  const silent = []
  const rows = (await pipeline(
    args.lenses,
    lens => call(reviewPrompt(lens, round, earlier, scope), { label: `review:${lens.key}:${tag}`, phase: reviewPhase, schema: FINDINGS }),
    (review, lens) => {
      if (!review) {
        silent.push(lens.key)
        log(`${tag}: the ${lens.key} reviewer returned nothing, so that lens went unreviewed`)
        return []
      }
      return parallel((review.findings || [])
        .map(f => ({ f, key: `${f.file}::${f.summary}` }))
        .filter(({ key }) => { if (seen.has(key)) return false; seen.add(key); return true })
        .map(({ f, key }) => () => call(verifyPrompt(f, lens, scope), { label: `verify:${lens.key}:${tag}`, phase: verifyPhase, schema: VERDICT })
          .then(v => {
            if (!v) seen.delete(key)
            return { ...f, lens: lens.key, round: tag, verdict: v, disposition: triage(v) }
          })))
    },
  )).flat().filter(Boolean)
  rows.forEach((r, i) => { r.id = `${tag}-${i + 1}` })
  return { rows, silent }
}

for (let round = 1; round <= MAX_ROUNDS; round++) {
  const { rows, silent } = await reviewRound({ round, tag: `r${round}`, scope: args.scope, earlier: table, seen, reviewPhase: 'Review', verifyPhase: 'Verify' })
  rows.forEach(r => { r.round = round })
  silentLenses.push(...silent.map(lens => ({ round, lens })))
  table.push(...rows)
  const fixes = rows.filter(r => r.disposition === 'fix')
  const warns = rows.filter(r => r.disposition === 'warn_or_doc')
  const unverified = rows.filter(r => r.disposition === 'unverified')
  log(`round ${round}: ${rows.length} found, ${fixes.length} fix, ${warns.length} warn_or_doc, ${rows.filter(r => r.disposition === 'drop').length} drop, ${rows.filter(r => r.disposition === 'refuted').length} refuted, ${unverified.length} unverified`)

  if (!FIX) {
    stopReason = `read-only: one round reviewed, nothing changed${silent.length ? `; the ${silent.join(', ')} lens returned nothing` : ''}`
    break
  }
  if (!fixes.length) {
    quiet = true
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

// The bookmark advances past a range only when every part of the run that covers it came back: a silent lens or an
// unverified finding is a gap, and in fix mode so is a loop that stopped with fixes no later round reviewed, or a gate
// that did not pass. Nothing moves on a gap, so the next review covers the same range again.
function bookmarkGap() {
  if (!BOOKMARK) return 'the review-scope hook passed no bookmark, so there is no base to record from'
  if (silentLenses.length) return 'a lens returned nothing'
  if (table.some(r => r.disposition === 'unverified')) return 'a finding went unverified'
  if (!FIX) return null
  if (!quiet) return 'the loop stopped before a round found nothing to fix, so its last fixes were never reviewed'
  if (fixReports.some(({ report }) => !report || report.gate_exit !== (GATE ? 0 : null))) return 'a fix round\'s gate did not pass'
  return null
}

// Runs one command through an agent, since the script itself cannot; the bookmark, the polish snapshots and the revert go through it.
function runCommand(command, label, phase) {
  return call(`${HANDS_OFF} Run this one command and nothing else (on Windows the interpreter is \`python\`, not \`python3\`), then report its exit status and its output verbatim:\n\n${command}`, { label, phase, schema: COMMAND_REPORT })
}

const SCOPE_SCRIPT = 'python3 ~/.claude/scripts/review_scope.py'
const TREE_ID = /^[0-9a-f]{40}([0-9a-f]{24})?$/

async function snapshot(label) {
  const done = await runCommand(`${SCOPE_SCRIPT} snapshot --repo "${BOOKMARK.repo}"`, label, 'Polish')
  const tree = done?.exit_status === 0 ? done.output.trim() : ''
  return TREE_ID.test(tree) ? tree : null
}

// The passes work over the skill's own scope, the whole working tree and unpushed commits, never over args.scope: a
// kept polish is recorded as `mark --polished` over the whole tree, and /commit's change_scope.py then skips both skills
// for every file in it, so a polish narrowed to the review's scope would mark files outside it polished unread.
function polishPrompt(skill, steps) {
  return `${CONTEXT}\n\nReviewed scope: ${args.scope}\n\n${HANDS_OFF}\n\nThe review of that scope has converged. Polish the repo's whole pending change set: read ~/.claude/skills/${skill}/SKILL.md in full and follow its Process over the scope that skill defines — the working tree and the unpushed commits — even where it is wider than the reviewed scope, since the workflow then records the whole tree as polished. Follow it with these differences, which the workflow sets because nobody is there to answer:\n- Run the commands in its Context section yourself; nothing has run them for you.\n- Apply every change the skill would propose instead of asking. Each one is shown to the user afterwards, and a later step reviews them all and reverts the whole polish if any one changed behaviour.\n${steps}\n\nReport every file you changed, one entry per change with one line on what changed and why, and nothing you did not change. Put what the skill would have asked the user, or suggested without doing, in notes.`
}

const CLEAN_STEPS = '- Skip its gate step: the workflow runs the gate once both polish passes are done.'
const DOCS_STEPS = '- Work in its sandbox as it says, then apply the patch it hands back to the repo with `git apply` and confirm with `git status --short` that the files it names changed. A patch that does not apply is reported in notes and left unapplied.\n- The code is already cleaned up; the docs describe it as it now stands.'

function gatePrompt() {
  return `${HANDS_OFF} Run the project's gate exactly as \`${GATE}\` from the repo at ${BOOKMARK.repo}, with its output redirected to a file and no pipe after it, and nothing else. Report its exit status, and the last 40 lines of that file as output. A pipe would replace the gate's exit status with the last command's.`
}

// The polish runs only over a review that would otherwise be recorded, so what it adds is the one change left
// unreviewed. Everything it cannot keep — a failed gate, a confirmed defect, a lens or a verifier that returned
// nothing — takes the whole polish back to the reviewed tree. A polish pass that returned nothing is the one outcome left
// unreverted, since what it edited is unknown; the run then records no bookmark, so /commit polishes that tree again.
async function polish() {
  const result = { polished: false, kept: false, detail: '', rows: [], notes: [], gap: null }
  if (!FIX) return { ...result, detail: 'not run: read-only' }
  if (reviewGap) return { ...result, detail: `not run: ${reviewGap}` }
  const before = await snapshot('polish:snapshot')
  if (!before) return { ...result, detail: 'not run: the tree could not be snapshotted', gap: 'the polish snapshot failed' }

  const passes = [['clean-code', CLEAN_STEPS], ['docs-relevance', DOCS_STEPS]]
  const reports = []
  for (const [skill, steps] of passes) reports.push([skill, await call(polishPrompt(skill, steps), { label: `polish:${skill}`, phase: 'Polish', schema: POLISH_REPORT })])
  for (const [skill, report] of reports) {
    for (const c of report?.changes || []) result.rows.push({ id: `polish-edit-${result.rows.length + 1}`, round: 'polish', lens: skill, file: c.file, summary: c.change, disposition: 'polish', outcome: 'applied', why: null })
    if (report?.notes) result.notes.push({ skill, notes: report.notes })
  }
  const dead = reports.filter(([, report]) => !report).map(([skill]) => skill)
  // A pass that died may have edited files it never reported, so nothing here can say what to take back.
  if (dead.length) return { ...result, detail: `the ${dead.join(' and ')} polish returned nothing; its edits, if any, are unreviewed in the tree`, gap: 'a polish pass returned nothing' }

  const after = await snapshot('polish:after')
  if (!after) return { ...result, detail: 'the polished tree could not be snapshotted', gap: 'the polish snapshot failed' }
  if (after === before) return { ...result, polished: true, detail: 'nothing to polish' }

  async function takeBack(reason) {
    // Only the passes' own edits: a polish review finding names a file it read, which the polish may never have touched.
    const edits = result.rows.filter(r => r.disposition === 'polish')
    const files = [...new Set(edits.map(r => r.file))]
    const done = await runCommand(`${SCOPE_SCRIPT} revert --repo "${BOOKMARK.repo}" --tree ${before} ${files.map(f => JSON.stringify(f)).join(' ')}`, 'polish:revert', 'Polish')
    const now = await snapshot('polish:reverted')
    edits.forEach(r => { r.outcome = `reverted: ${reason}` })
    // A file the passes changed without reporting it survives the revert, and so does a peer's write; either leaves a
    // tree no review covered, which is reported rather than reverted further.
    if (done?.exit_status !== 0 || now !== before) return { ...result, detail: `${reason}; the revert left the tree differing from the reviewed one, whose snapshot is ${before}: ${done ? done.output.trim() : 'the revert agent returned nothing'}`, gap: 'the polish revert did not restore the reviewed tree' }
    return { ...result, detail: `reverted: ${reason}` }
  }

  if (GATE) {
    const gate = await call(gatePrompt(), { label: 'polish:gate', phase: 'Polish', schema: COMMAND_REPORT })
    if (gate?.exit_status !== 0) return takeBack(gate ? `the gate failed after the polish:\n${gate.output}` : 'the gate agent returned nothing')
  }

  const scope = `Only the changes a clean-up pass just made to ${BOOKMARK.repo}, and nothing else: \`git -C "${BOOKMARK.repo}" diff ${before} ${after}\`. A clean-up must not change behaviour, so any behaviour it changed is a defect, however small.`
  const { rows, silent } = await reviewRound({ round: 1, tag: 'polish', scope, earlier: [], seen: new Set(), reviewPhase: 'Polish review', verifyPhase: 'Polish review' })
  result.rows.push(...rows)
  if (silent.length) return takeBack(`the ${silent.join(', ')} lens returned nothing over the polish`)
  if (rows.some(r => r.disposition === 'unverified')) return takeBack('a finding in the polish went unverified')
  // Any confirmed finding, whatever its realism: the triage's warn_or_doc and drop route a rare or unreached case away
  // from code, but nothing runs a fixer after the polish, and a clean-up that changed behaviour at all is not one to keep.
  const defects = rows.filter(r => r.verdict?.real)
  if (defects.length) return takeBack(`the polish review confirmed ${defects.map(r => r.id).join(', ')}`)
  return { ...result, polished: true, kept: true, detail: `kept: ${result.rows.filter(r => r.disposition === 'polish').length} change(s), reviewed` }
}

// Taken before the polish adds its own rows: a finding over a polish that was then reverted is no gap in the review.
const reviewGap = bookmarkGap()
const polished = await polish()
table.push(...polished.rows)

async function recordBookmark() {
  const gap = reviewGap || polished.gap
  if (gap) return { recorded: false, detail: `not recorded: ${gap}` }
  // With nothing applied the tree at launch is the reviewed one, even if something else wrote to the repo meanwhile.
  // After fixes or a kept polish it is the tree now, which also takes in anything another writer changed while the run was going.
  const tree = fixReports.length || polished.kept ? '' : ` --tree ${BOOKMARK.tree}`
  const done = await runCommand(`${SCOPE_SCRIPT} mark --repo "${BOOKMARK.repo}" --base ${BOOKMARK.base}${tree}${polished.polished ? ' --polished' : ''}`, 'bookmark', 'Bookmark')
  if (!done) return { recorded: false, detail: 'not recorded: the bookmark agent returned nothing' }
  return { recorded: done.exit_status === 0, detail: done.output }
}

const bookmark = await recordBookmark()

return {
  stop_reason: stopReason,
  bookmark,
  polish: { detail: polished.detail, notes: polished.notes },
  note: 'Present the triage table to the user as a triage, not as "all fixed". Say whether the bookmark was recorded, and why not when it was not. Rare and theoretical items are reported with their ratings; another round is not offered by default. An unverified finding is neither confirmed nor disproved, and a lens in silent_lenses was never reviewed: say so rather than counting either as clean. Rows with disposition polish are clean-up edits, kept or reverted as their outcome says; polish.notes holds what the clean-up passes would have asked about.',
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
    why: r.disposition === 'polish' ? null : r.verdict?.reasoning ?? 'the verifier returned nothing, so this finding is neither confirmed nor refuted',
  })),
  fixes: fixReports,
}
