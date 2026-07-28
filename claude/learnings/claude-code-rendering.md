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

# Comments render as literal text — nothing hides them

Claude Code's terminal markdown renderer shows both HTML comments
(`<!-- x -->`) AND markdown link-reference "comments" (`[//]: # (x)`) as
literal text. Neither is hidden the way GitHub's HTML renderer hides them —
a common wrong assumption is that an HTML comment is invisible in the
terminal; it is not (verified empirically). There is no settings.json key,
env var, or output style that changes markdown rendering to suppress a
pattern. So any marker/sentinel a hook asks the model to emit WILL be
visible in the agent's terminal. Only zero-width Unicode renders invisibly,
at the cost of the model reliably reproducing exact invisible bytes.

# Rewriting displayed output: the MessageDisplay hook is per-DELTA

`MessageDisplay` is the only hook that can rewrite what the user sees. It
returns `hookSpecificOutput.displayContent`, which replaces the on-screen
text **display-only** — "the transcript and what Claude sees keep the
original", so `Stop.last_assistant_message` (read from the transcript) is
unaffected. That sounds perfect for stripping a marker from the display
while keeping it machine-readable — but it isn't usable for a trailing
marker: the compiled binary's Zod schema (the public docs are too thin;
`grep -a displayContent claude.exe`) describes `displayContent` as
replacing **"the delta"**. MessageDisplay fires per STREAMING CHUNK, not
once per whole message. A trailing marker spans token-boundary deltas, a
stateless per-delta hook can't tell which delta is last, and it forks
synchronously per chunk with a ~10s timeout that blocks TUI rendering.

Hooks that can mutate what the user sees: `MessageDisplay` (`displayContent`,
per-delta, display-only), `PreToolUse` (`updatedInput`), `PostToolUse`
(`updatedToolOutput`), `PermissionRequest` (`updatedInput`). None can
rewrite a whole assistant message after the fact. When the docs are thin on
a hook's payload/behavior, the installed `claude.exe` embeds the
authoritative Zod schemas — grep the binary for the field name.
