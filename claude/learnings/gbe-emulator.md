# GBE (Goldberg Steam Emulator) — gbe_fork

Notes on Detanup01's [gbe_fork](https://github.com/Detanup01/gbe_fork) of the Goldberg Steam Emulator. Local copy at `D:/projects/games/gbe_fork/`.

## `steam_appid.txt` resolution priority

When a game loads GBE's `steam_api64.dll` and calls `SteamAPI_Init`, GBE resolves the app ID in this priority order (source: `dll/settings_parser.cpp`, function `parse_steam_app_id`, lines 560–643):

1. **Env vars** — checks `SteamAppId`, `SteamGameId`, `SteamOverlayGameId` (in that order; later wins if multiple set)
2. **`<game_settings_path>/steam_appid.txt`** — `get_game_settings_path()` returns the `steam_settings/` directory next to the loaded DLL. This is where `generate_emu_config` writes the file.
3. **cwd `steam_appid.txt`** — current working directory of the process
4. **`<program_path>/steam_appid.txt`** — directory of the running executable

First non-zero result wins.

### Implication for tooling

Once GBE replaces `steam_api64.dll`, an outer `steam_appid.txt` (placed next to the exe) is **redundant** — #2 always wins as long as `steam_settings/steam_appid.txt` exists. Don't add it unless there's a verified non-GBE path that reads it (the original Valve `steam_api64.dll` reads from cwd as a "no-Steam-running" dev bypass, but that path is dead once GBE is loaded).

The `steam_gameserver.cpp` flow is similar but only checks game_dir → cwd (no env vars, no `steam_settings/`).

## Where `generate_emu_config` writes things

`gbe_fork_tools/generate_emu_config/generate_emu_config.exe` (separate repo: [gbe_fork_tools](https://github.com/Detanup01/gbe_fork_tools)) writes to `<cwd>/output/<APP_ID>/steam_settings/`:
- `achievements.json` — array of achievement objects: `name`, `displayName` (string or `{lang: ...}`), `description` (same), `icon`, `icongray`, `hidden`
- `achievement_images/` — `.jpg` files (named per the `icon` paths)
- `configs.main.ini`, `configs.app.ini`, `configs.overlay.ini`, `configs.user.ini`
- `steam_appid.txt` — written **inside** `steam_settings/`, not at game root
- `steam_interfaces.txt` — populated separately by `generate_interfaces_x64.exe`
- `depots.txt`, `supported_languages.txt`, `stats.json`, `account_avatar.jpg`, `load_dlls/`, `sounds/`

**Stringly-typed `hidden` field:** `generate_emu_config` emits `hidden` as a quoted integer (`"hidden": "0"` / `"hidden": "1"`), not a JSON number. A C# `int` field with `[JsonPropertyName("hidden")]` throws on deserialization. Either omit the field (System.Text.Json ignores unknown keys) or set `JsonNumberHandling.AllowReadingFromString` on the options. Observed in Aphelion (appid 1966410). The same may apply to other numeric-looking fields — treat all values defensively.

**Deeply-nested `steam_settings/` in UE-based games:** Some Unreal Engine games (e.g. Aphelion) ship `steam_settings/` deep inside the game folder — `<game>/Engine/Binaries/ThirdParty/Steamworks/Steamv157/Win64/steam_settings/`. The DLL `steam_api64.dll` lives in that same `Win64/` directory. So `Path.GetFileName(parentOfSteamSettings)` returns "Win64" — not a usable game name. Derive the human-readable name from the first-level subfolder under the configured games root, not from the parent of `steam_settings/`.

Auth: reads `GSE_CFG_USERNAME` / `GSE_CFG_PASSWORD` env vars or `my_login.txt` beside the exe. **Steam Guard 2FA** prompts interactively on first run — cannot complete in non-interactive sessions (e.g. agent-driven). If the game already has a valid `steam_settings/`, prefer reusing it.

## GSE Saves location

GBE writes runtime save data (achievement unlocks, stats) to:
- Windows: `%appdata%/GSE Saves/<APP_ID>/`
- Linux: `~/.local/share/GSE Saves/<APP_ID>/`

The `<APP_ID>` directory is created on **first achievement unlock or stat write**, not on launch. Don't expect it to exist after just starting the game.

Older Goldberg installs may have data at `%appdata%/Goldberg SteamEmu Saves/<APP_ID>/` instead.

## Two GBE-derived overlays at play in this workspace

- **GBE's experimental overlay** — built into `release/experimental/x64/steam_api64.dll`, hooks DX/GL/Vulkan via `ingame_overlay`. Can trigger anti-tamper (e.g. Red Dead Redemption error 25D11007). Disable via `configs.overlay.ini` → `enable_experimental_overlay=0` and use `release/regular/x64/steam_api64.dll` instead.
- **achievement-overlay** (`D:/projects/games/achievement-overlay/`, installed at `C:/Programs/achievement-overlay/`) — standalone WPF app that monitors `%appdata%/GSE Saves/` filesystem changes and shows toast-style notifications. No game process interaction. Survives anti-tamper. Its `GameCache` scans `gamesPaths` recursively for `steam_appid.txt`, detecting it in either the game root or inside `steam_settings/` (the `generate_emu_config` placement). The displayed game name is the first-level subfolder under the configured games root, so deeply-nested UE layouts render correctly (e.g. `C:\Games\Aphelion\...\Win64\steam_settings\` → "Aphelion").
