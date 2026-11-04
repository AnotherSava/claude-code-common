# Renaming a Tauri app's `identifier`

`identifier` in `src-tauri/tauri.conf.json` drives `app_data_dir()`. Changing
it moves the runtime data folder to a new path; existing `config.json`,
saved window position, OAuth credentials, log files, etc. at the old path
are orphaned.

## Resolved path per platform

| Platform | Path                                                            |
|---       |---                                                              |
| Windows  | `%APPDATA%\<identifier>\`                                       |
| macOS    | `~/Library/Application Support/<identifier>/`                   |
| Linux    | `$XDG_CONFIG_HOME/<identifier>/` (or `~/.config/<identifier>/`) |

## Migration strategies (pick one before renaming a published app)

1. **Read-both-prefer-new at startup:** look up the old path on first
   launch, copy contents to the new path, delete or leave the old. Cheap
   to write; one-shot logic per user.
2. **Document the manual copy:** release notes tell users to copy
   `%APPDATA%\com.old\` → `%APPDATA%\com.new\`. Zero code change but
   easy for users to skip.
3. **Accept the reset:** for solo/personal projects, just let users
   reconfigure. Config hot-reloads on save so the pain is bounded.

## Also touched by an identifier rename

Anything that hardcoded the old identifier needs the same update:

- `src-tauri/tauri.conf.json` — the `identifier` field itself
- Docs that quote the appdata path (README, `docs/index.md`, `docs/pages/development.md`, `CLAUDE.md`)
- Deploy settings naming the appdata path (`CONFIG_DEST=%APP_CONFIG%/<identifier>/config.json` in `config/deploy.env`, or `SECRET_FILE`), and any per-machine `config/deploy.local.env` — that one is ignored, so a fresh `git status` won't surface it
- Anything that derived a temp-dir prefix or log target from the crate name

## Related side effects

The identifier also feeds the NSIS uninstaller key on Windows — old and
new installs may both appear in "Apps & features" until users uninstall
the old one. (Verify against the actual bundler output before claiming
this in user-facing docs.)
