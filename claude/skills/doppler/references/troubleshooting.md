# Doppler failure modes

Every row here was observed in a real session. The symptom usually points somewhere other than the
cause, which is why guessing at a fix wastes more time than reading this.

## The command fails

| Symptom | Cause | Fix |
|---|---|---|
| `You must specify a project` / `The fallback file does not exist` | The directory was never bound; a committed `doppler.yaml` is not enough | Run `doppler setup --no-interactive` in the repo |
| `Unable to fetch secrets from the Doppler API` | Not logged in on this machine, or the project/config pair doesn't exist | Check `doppler projects` and `doppler configs -p <proj>`; if unauthenticated, the user runs `doppler login` in a real terminal |
| `Incorrect function` on `doppler login` | It was run through Claude Code's `!` prefix, which gives it no TTY | The user runs it in a real terminal — this step is never Claude's |
| `doppler: command not found` | CLI not installed on this machine | See the install section in `project-setup.md` |
| Auto-mode denies `doppler secrets get … --plain` as "Credential Materialization" | The classifier blocks echoing a secret to stdout | Derive a boolean via `doppler run -- …` instead of printing the value; don't route around it |

## The command succeeds and the value is wrong

These are the expensive ones — nothing errors, so the damage surfaces much later.

| Symptom | Cause | Fix |
|---|---|---|
| The secret is empty, truncated, or was never set | An unquoted value: `&` backgrounded the command, `!` hit history expansion, a space split the argument | Quote it — `"value"` for `& % ( )` and spaces, `'value'` when it may contain `$`, a backtick, `!`, or `"`. Better: pipe via stdin |
| A path value comes back as `C:/Program Files/Git/...` | Git Bash on Windows rewrites any argument that *starts* like a POSIX path. A value with a non-slash prefix (`file:/data/db.sqlite`) is left alone | Pipe via stdin, or prefix with `MSYS_NO_PATHCONV=1`. Details in `~/.claude/learnings/docker-windows-git-bash.md` |
| The value has a trailing newline | It was fed in with `< file`, which keeps the file's final newline | Use `printf '%s' "$(cat <file>)" \|` and confirm with the digest check in `project-setup.md` |
| The plaintext still printed despite `--visibility masked` | Masked is a dashboard access attribute, not output redaction. The set-time confirmation table prints the value, and later reads return it in the clear | Use `--silent`. Combine `--silent --visibility masked` for both effects |
| A secret leaked into the transcript even with `--silent` | The command ran through the `!` prefix, which records the *input* — `--silent` only suppresses output | Have the user run it in a separate terminal, or use the dashboard |
| The app reads a stale value | A leftover `.env` plus a `dotenv` import wins over, or races with, `doppler run` | Delete the `.env`, drop the `dotenv` import and devDependency, and route every secret-reading script through `doppler run` |

## The wrong coordinates

| Symptom | Cause | Fix |
|---|---|---|
| `-p sava` is rejected or behaves oddly | `sava` is the workplace, not a project | Use the per-app project from `doppler projects` |
| A secret is set but the app can't see it | It went into `prd` (or `stg`) while the app runs on `dev` | Default to `dev` everywhere except a genuine production task |
| A production credential turns up in a local build | One command reached both a local and an outward-facing config | Keep `deploy` and `publish` as separate verbs with separate configs — see the `feedback_deploy_publish_separate_verbs` memory |
