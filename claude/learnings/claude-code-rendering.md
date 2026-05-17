# Claude Code rendering: ANSI escapes & code blocks

ANSI escape sequences (`\x1b[48;5;236m`, `\x1b[0m`, etc.) embedded inside
a code block in a response message are NOT interpreted by Claude Code's
markdown renderer — they appear as literal text (`[48;5;236m ...`).

Practical consequence: terminal-coloring techniques applied to a script's
output don't survive the round-trip when the script's stdout is captured
via the Bash tool and re-pasted in a response. Zebra-striping, syntax
highlighting, ANSI-color logs — all stripped at the render layer.

For scripts that are sometimes invoked via Claude Code and sometimes from
a real terminal, guard ANSI emission with `sys.stdout.isatty()` (Python)
or `[ -t 1 ]` (bash) so the output stays clean when captured and colored
when not.

The user's view of a `/skill` invocation comes from the model's response
markdown, not the script's raw stdout, so colors emitted by the script
don't reach the user even if `isatty()` is forced on. Only a directly-
attached terminal (e.g. `python3 script.py` from your own shell prompt)
will render the colors.

## Quick probe

To verify in any session:

    printf '\x1b[48;5;236m test \x1b[0m\n'

If the output shows `[48;5;236m test [0m` literally instead of a colored
"test" string, ANSI is being stripped or not interpreted along the path
your output is taking.
