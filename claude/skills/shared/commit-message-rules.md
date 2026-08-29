# Commit Message Rules

## Format

Conventional Commits with optional scope:

```
type(scope): concise summary of the change

Longer description explaining the motivation and what was done.
Summarize the "why" not just the "what".
```

- **type**: `feat`, `fix`, `refactor`, `docs`, `chore`, etc. — pick based on the primary change
- **scope**: the subsystem affected (e.g. `engine`, `render`, `extract`, `sidepanel`)

## Validation checklist

- Imperative mood ("add" not "added")
- Subject line ≤ 50 characters, body lines wrapped at 72 characters
- No trailing period
- Type prefix not repeated in description (e.g. not "refactor: refactor...")
- No capitalized first word after type prefix
- Do not list files or file-level descriptions in the body
- **Body is at most one short paragraph, and usually absent** (see below)
- Explain *why* only where the reason is yours to explain (see below)

## Match the body to the change's reach

**Be concise. Most commits need no body at all, and one that has a body needs at most a short
paragraph.** The default is a subject line. Add a body only when the diff cannot answer a
question a later reader will actually have — then answer that question and stop.

A body running past a few lines is almost always a session recap or a rediscovered argument,
and neither belongs in the log: an investigation goes in a learning, a preference goes in a
memory, and a decision goes in the document it governs. `git log` is read to find *which*
commit changed something, rarely to relive why.

Symptoms that the body has outgrown the change: more than one paragraph; narrating what was
considered and rejected; restating a comment the diff already carries; explaining the mechanism
instead of the intent; recounting how the problem was found. If the reasoning is genuinely worth
keeping, it is worth keeping somewhere it will be re-read — which a commit message never is.

- **A data-only change gets a subject and almost nothing else.** Adding, removing, or
  correcting entries in a data file (a place, a record, a list value) has the least effect on a
  project of any change it can carry, so keep the message proportional: write the subject, and
  add at most one short line for something the subject can't hold. Regenerated artifacts need
  no mention at all.
- **Don't explain the data in the commit.** How an entry was chosen, pinned, spelled, or
  verified is project knowledge — it belongs in project memory, where the next session will
  read it, not in a message nobody consults while adding the next entry.
- Save the "why" body for code, schema, and workflow changes, where a later reader has to
  reconstruct intent from the diff.
- **Explain the reason only when the reason is yours.** A change the user asked for needs no
  justification: they know why they wanted it, and anything written there is a guess at their
  motive dressed up as a record. State what the change does and stop. A change that came from
  your own initiative — a bug fix, a refactor, a defensive guard, a rename nobody requested —
  is the opposite: nothing in the diff says why you thought it was worth doing, so that belongs
  in the body. The test is who would be surprised to find the change in the log.
- **Don't restate the code's own comments.** Reasoning already written beside the code is read
  by everyone who reads the diff, and repeating it in the message only gives the two copies room
  to drift. Put in the body what the diff cannot carry — a measurement, a rejected alternative,
  an external constraint.

## Attribution

- Do NOT include any AI attribution or Co-Authored-By trailers
- Commits should be authored solely by the user
- Do not include any "Generated with Claude" messages

## Author identity

Before committing, verify that `git config user.name` is not "Claude" or similar AI attribution. If it is, remove the local override with `git config --unset user.name` and `git config --unset user.email` so the global config (which has the real user identity) takes effect. Never hardcode author names in commit commands.

## Examples

Good commit messages:
- `feat: add marker holder model`
- `refactor: consolidate edge filtering logic in edgefilters module`
- `chore: update README with published models, add missing deps`
- `feat: add fillet radius reuse and arc support to Pencil`

Bad commit messages:
- `feat: added new marker holder model to the project` (past tense, verbose)
- `refactor: refactored edge filtering` (redundant — type already says refactor)
- `update stuff` (no type, vague)
- `fix: fix bug` (no useful information)
- `feat: add SmartBox.with_delta() class method and update all callers to use it` (too long, move details to body)
- `feat: add keepPathFrom site rule for path trimming` with body `Strips SEO slug segments before an anchor like dp or gp, producing cleaner Amazon URLs.` (body repeats what the subject already says — body should add context not visible from the diff, not rephrase the subject)
