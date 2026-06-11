# PowerShell → docker run → bash -c quoting

Inline shell snippets passed through PowerShell into containers (`docker run … bash -c "…"`) break in layered, hard-to-spot ways. Lost several round-trips to this; the rule that ends the pain:

**For anything beyond one trivial command, write a `.sh` script, mount it, and run it** (`-v ./scripts:/work/scripts:ro … bash /work/scripts/run.sh`). Scripts also become reproducible artifacts instead of throwaway one-liners.

## Failure modes observed (PowerShell 7, Windows)

| Symptom | Cause |
|---|---|
| Bash var silently empty: `python3 script.py $P 'arg'` → wrong argv count | Inside a **double-quoted** PS string, `$P` is interpolated by *PowerShell* (undefined → empty) before bash ever sees it. `\$P` does NOT protect it — backslash isn't a PS escape; PS still interpolates `$P` after the backslash |
| `unexpected EOF while looking for matching '` | Single quotes inside the bash snippet collide with PS quoting after one level of nesting |
| `$?` mangled: `echo EXIT:$?` prints `EXIT:True` | PS interpolates its own `$?` (a boolean) into the string |
| grep/sed patterns with `"`/`[`/`\` corrupted | Each layer (PS → docker CLI → bash) strips or rewrites one level of escaping |

## When inline is unavoidable

- Use a **single-quoted PowerShell string** for the whole `bash -c '…'` argument — PS doesn't interpolate inside single quotes; then use double quotes inside the bash snippet.
- Keep bash-side `$vars` only under PS single quotes; there is no reliable escape for them under PS double quotes.
- Heredocs inside mounted scripts work fine and are the right home for embedded Python (`python3 <<'EOF' … EOF`).
