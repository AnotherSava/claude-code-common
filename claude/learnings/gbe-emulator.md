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

## Achievement icon path resolution (runtime)

When the overlay loads an achievement icon, GBE (`dll/steam_user_stats_achievements.cpp`, ~lines 99–110) tries two locations, in order:
1. The `icon` value **verbatim**, relative to `steam_settings/` (e.g. `steam_settings/achievement_images/ACH.jpg`).
2. If not found, **prefixed with `achievement_images/`** — `steam_settings/achievement_images/<icon>`.

This fallback is **unconditional** (always tried second, regardless of whether the value already contains a subfolder), so configs that store a bare filename like `"icon": "ACH.jpg"` still resolve. The CHANGELOG records the intent: *"prefer original paths of achievement icons first, then fallback to `achievement_images/`"*. Any tool reading GBE achievement configs should mirror this (verbatim → `achievement_images/`) or it'll miss icons for bare-filename configs (generate_emu_config, manual setups).

## GSE Saves location

GBE writes runtime save data (achievement unlocks, stats) to:
- Windows: `%appdata%/GSE Saves/<APP_ID>/`
- Linux: `~/.local/share/GSE Saves/<APP_ID>/`

The `<APP_ID>` directory is created on the **first write of any kind**, not on launch — whichever happens first:
- **Playtime counter** (`dll/playtime.cpp`): writes a playtime file ~60s into the session (`since_save >= 60`) and again on clean shutdown (destructor).
- **Cloud save** (`remote/` subfolder) and **stats** writes.
- **Achievement unlock**.

So the folder (often containing just `remote/` and a playtime file) can exist well before any achievement is unlocked. But `achievements.json` **specifically** is written only on the **first achievement unlock or clear** (`save_achievements()` in `dll/steam_user_stats_achievements.cpp`, called from `SetAchievement`/`ClearAchievement`) — never at init, and not pre-populated from the schema. To detect "the emulator ran for this game," watch for the `<APP_ID>` folder; to detect actual unlocks, watch `<APP_ID>/achievements.json`.

Older Goldberg installs may have data at `%appdata%/Goldberg SteamEmu Saves/<APP_ID>/` instead.

## Two GBE-derived overlays at play in this workspace

- **GBE's experimental overlay** — built into `release/experimental/x64/steam_api64.dll`, hooks DX/GL/Vulkan via `ingame_overlay`. Can trigger anti-tamper (e.g. Red Dead Redemption error 25D11007). Disable via `configs.overlay.ini` → `enable_experimental_overlay=0` and use `release/regular/x64/steam_api64.dll` instead.
- **achievement-overlay** (`D:/projects/games/achievement-overlay/`, installed at `C:/Programs/achievement-overlay/`) — standalone WPF app that monitors `%appdata%/GSE Saves/` filesystem changes and shows toast-style notifications. No game process interaction. Survives anti-tamper. Its `GameCache` scans `gamesPaths` recursively for `steam_appid.txt`, detecting it in either the game root or inside `steam_settings/` (the `generate_emu_config` placement). The displayed game name is the first-level subfolder under the configured games root, so deeply-nested UE layouts render correctly (e.g. `C:\Games\Aphelion\...\Win64\steam_settings\` → "Aphelion").

## Hidden achievement descriptions (Steam redacts; SteamDB via Firecrawl)

Steam's Web API `GetSchemaForGame` returns `description: ""` for `hidden=1` achievements (`displayName` is still present). The real text lives on SteamDB at `https://steamdb.info/app/<APPID>/stats/`, **but SteamDB is behind Cloudflare**. A plain `HttpClient`/curl gets **403 even with a valid `cf_clearance` cookie** — the cookie is bound to the browser's TLS/JA3 fingerprint (plus IP and a short-lived `__cf_bm` cookie), which a non-browser client can't reproduce; no User-Agent fixes it. SteamHunters and Completionist.me are also Cloudflare-blocked.

Working automated path: the **Firecrawl API** — a hosted scraper that solves Cloudflare and returns markdown:
- `POST https://api.firecrawl.dev/v1/scrape`, header `Authorization: Bearer <key>`, body `{"url": "...", "formats": ["markdown"], "onlyMainContent": true}`. The markdown is at `data.markdown` in the JSON response. (Firecrawl free tier is limited but plenty for one-off per-game configs.)
- SteamDB stats markdown linearizes per achievement as: icon line(s) `![...]`, **DisplayName**, **description** (hidden ones prefixed `_Hidden achievement:_`), **percent** (`77.8%`), **API name** (a single token, e.g. `Beginning`), **date**. Parse by anchoring on the percent line: API name = the next non-empty line, description = the previous line (strip the `_Hidden achievement:_` marker). Match back to the schema by **API name**.

## Windows Defender flags GBE binaries as PUA

Defender quarantines GBE's `steam_api64.dll` and the release `.7z` as potentially-unwanted software (false positive). Reading a flagged file throws `IOException` with HRESULT `0x800700E1` (ERROR_VIRUS_INFECTED) or `0x800700E2` (ERROR_VIRUS_DELETED). To proceed programmatically:
- Add exclusions with elevated PowerShell: `Add-MpPreference -ExclusionPath '<path>'`. Needs admin → launch via `ProcessStartInfo { UseShellExecute = true, Verb = "runas" }` (one UAC prompt). A declined UAC throws `Win32Exception` with `NativeErrorCode == 1223` (ERROR_CANCELLED).
- Exclude **both** the GBE cache folder **and** the game folder (the emulator DLL is copied into the game, and Defender re-scans it there).
- Download the `.7z` **into the (excluded) GBE folder**, not `%TEMP%` — then a single folder exclusion covers the archive read *and* the extracted DLLs. (A `%TEMP%` download stays scanned even after the GBE-folder exclusion, so extraction keeps failing.)

## Playnite achievements add-on: SuccessStory → "Playnite Achievements"

The Playnite SuccessStory plugin (Lacro59, plugin GUID `cebe6d32-8c46-4459-b993-5a5189d60788`) has been forked/rebranded to **"Playnite Achievements"** (justin-delano → Santodan fork; extension id `PlayniteAchievementsSantodan`). The fork uses a **different plugin GUID `e6aad2c9-6e06-4d8d-ac55-ac3b252b5f7b`** and stores per-game data in a **SQLite DB** (`achievement_cache.db`, WAL mode) under its own `ExtensionsData/<guid>/` — not the per-game JSON files SuccessStory wrote.

The old SuccessStory mechanism — map a Playnite game GUID → Steam AppID in `ForcedSteamAppIds` inside `cebe6d32/config.json`, after which it fetches the Steam schema and merges unlock state from GSE Saves — is **gone in the fork**: its `config.json` has no `ForcedSteamAppIds`. The fork resolves achievements per game by **provider**; an emulated/non-Steam game logs "Skipped … without a capable provider" until you **override its provider to Local** (a per-game override stored in the SQLite DB — no clean JSON to edit). The fork also ships its own local-achievement realtime notifications.

Implication for tooling: a config-file integration only works on the legacy SuccessStory install (`cebe6d32` + `ForcedSteamAppIds`). For the fork there's no JSON to write; direct SQLite writes are fragile across versions. Note the Playnite game's library name (e.g. "Frostpunk 2: Deluxe Edition") often differs from the game folder name — match per-game entries by the Playnite name, not the folder.
