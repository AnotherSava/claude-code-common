---
name: annotate
description: Annotate any file in Plannotator's browser UI. Markdown and HTML files are passed through directly; other files are wrapped in a temporary `.md` with a fenced code block, annotated, then the temp file is deleted.
---

# Annotate

Use this skill when the user wants to annotate an arbitrary file in Plannotator — not just markdown/HTML.

Argument: a single file path.

## Behavior

1. **`.md` or `.html` (case-insensitive)** — invoke the `plannotator-annotate` skill on the file directly.

2. **Anything else:**
   - Create a temp `.md` in the system temp dir: `mktemp -t annotate.XXXXXX.md` (Git Bash / WSL) or `New-TemporaryFile` renamed to `.md` (PowerShell).
   - Write into it:

     ````markdown
     # `<original-path>`

     ```<lang>
     <file contents verbatim>
     ```
     ````

     `<lang>` is the language tag inferred from the original file's extension (see table). Omit the tag entirely for unknown extensions.
   - Invoke the `plannotator-annotate` skill on the temp file path.
   - **Treat returned annotations as if they referred to the original file.** When you address them — edits, follow-ups, mental model — the original path is the source of truth. The temp `.md` is a presentation surface only.
   - Delete the temp file when done (success, failure, or no annotations). Use a `trap`/`try-finally` so cleanup runs even on errors.

## Extension → language tag

| Extension(s) | Tag |
|---|---|
| `.py` | `python` |
| `.js`, `.mjs`, `.cjs` | `javascript` |
| `.ts` | `typescript` |
| `.tsx`, `.jsx` | `jsx` |
| `.rs` | `rust` |
| `.go` | `go` |
| `.java` | `java` |
| `.kt`, `.kts` | `kotlin` |
| `.cs` | `csharp` |
| `.cpp`, `.cc`, `.cxx`, `.hpp`, `.h` | `cpp` |
| `.c` | `c` |
| `.sh`, `.bash` | `bash` |
| `.ps1` | `powershell` |
| `.json` | `json` |
| `.yaml`, `.yml` | `yaml` |
| `.toml` | `toml` |
| `.xml` | `xml` |
| `.css`, `.scss` | `css` |
| `.sql` | `sql` |
| `.rb` | `ruby` |
| `.php` | `php` |
| `.swift` | `swift` |
| `.ahk` | `autohotkey` |
| `.lua` | `lua` |
| `.gradle` | `groovy` |
| `.dockerfile`, `Dockerfile` | `dockerfile` |

Unknown extension: emit a bare ` ``` ` fence with no language tag.

## Notes

- Do not transform or summarize the file content — copy it byte-for-byte into the fence.
- For very large files (> ~1 MB), warn the user before proceeding — Plannotator's UI may struggle.
- Binary files are out of scope — refuse if the file is not plain text.
