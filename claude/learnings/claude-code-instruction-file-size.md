# Claude Code's instruction-file size warning

Claude Code warns at session start when instruction files are large, in one of two forms:

- `‼ N instruction files add up to X chars, over the Y-char total limit · largest: … · /memory to free up context`
- `<file> is over the Z-char limit (N chars)`

Both come from its `large-memory-files` check, and both are warnings only: nothing is truncated or dropped. `/doctor` words the same condition as "Instruction files will impact performance". The cost is context spent on every turn, not missing instructions. Verified 2026-09-28 on Claude Code 2.1.283: a session with a 146.8k-char project `CLAUDE.md` and a 77.1k-char global one got the total-limit warning and still received both files whole, their closing sections included.

## The limits

Both limits scale with the model's context window:

- **Per file:** `max(40_000, round(context_tokens × 0.05 × chars_per_token))`.
- **Total:** `max(120_000, per-file limit)`. A file already over the per-file limit gets its own warning and is left out of the total.

On a 1M-context model both came to 150,000 chars, which implies 3 chars per token. The same formula gives 40,000 per file and 120,000 total on a 200k-context model — derived from the code, not observed. The auto-memory index and managed settings are excluded by path; in the verified case the two `CLAUDE.md` files were the only ones counted.

## Reading the source

The message text and the limit functions are in the bundled `claude.exe` of an npm global install, under `@anthropic-ai/claude-code/bin/`. `grep -a -o -E ".{600}total limit.{300}"` over it lands on the render function, and the limit functions sit beside the `large-memory-files` id. Minified names change every release, so search by the message text rather than by a function name.
