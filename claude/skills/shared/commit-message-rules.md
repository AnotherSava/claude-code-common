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
- Focus on why the changes were made, not just what

## Match the body to the change's reach

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
