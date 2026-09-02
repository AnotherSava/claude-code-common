# GBE (Goldberg Steam Emulator) — gbe_fork

Notes on Detanup01's [gbe_fork](https://github.com/Detanup01/gbe_fork) of the Goldberg Steam Emulator, cloned locally under the games projects directory.

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

## A game usually has more than one `steam_settings/`, and some are hidden

Two traps for any tool that locates a game's config by scanning for `steam_appid.txt` or `steam_settings/`:

**Several folders per install, holding different things.** A repack commonly drops a decorated `steam_settings/` at the game root while the emulator reads a bare one beside the DLL it loads — `bin/coldclient/`, `www/greenworks/lib/` (NW.js/greenworks games), `…/Binaries/Win64/`. GBE resolves its config folder from `get_full_program_path()`, the directory of the **loaded emulator DLL**, so the nested copy is the one that counts at runtime. But the root copy is frequently the *richer* one — it is where a repack puts a themed `configs.overlay.ini`, `fonts/` and `sounds/`, none of which the emulator ever reads there. Across a real games library roughly a third of installs had more than one. Keying a cache by appid and letting the last scanned win discards the others silently and in filesystem order; collect them all, then decide per use whether you want the authoritative one (schema, icons) or the union (stated preferences).

**Repacks mark `steam_settings/` hidden.** .NET's default `EnumerationOptions.AttributesToSkip` is `Hidden | System`, so such a folder is never enumerated — see `dotnet-filesystem-windows.md`. A game whose *only* config folder is hidden is invisible to a default recursive scan, with no error to explain it.

## Nothing but a third party writes `configs.overlay.ini`

The four config files — `configs.app.ini`, `configs.main.ini`, `configs.overlay.ini`, `configs.user.ini` — merge into **one key space**, where the `[section]` decides a key's meaning and the *filename does not*, with the **first file to define a key winning** in that order. Local `steam_settings/` then beats the global `%APPDATA%\GSE Saves\settings\`, per key.

The emulator only ever writes back `configs.user.ini` (account name, Steam ID, language, country) via `save_global_ini_value`. The release README's "some default configurations are saved" means that file alone. Everything else arrives from a repack, an older generator, or the user renaming `steam_settings.EXAMPLE/configs.overlay.EXAMPLE.ini` by hand — which is why such a file is best read as *a statement of what someone wanted*, not as a description of what the emulator is currently doing. It is routinely present in installs where it is never read at all: the **regular** (non-experimental) GBE build contains no overlay code and ignores the file entirely.

Parser quirks (vendored SimpleIni, configured without quote handling):

- **`[overlay::appearance]` keys are effectively case-sensitive** — the parser enumerates keys and compares stored spellings with `std::string::compare`, so `font_size=22` is silently discarded. `[overlay::general]` uses `GetBoolValue` and *is* case-insensitive. Worse: if a local file and the global one spell one key differently, SimpleIni keeps the first-inserted spelling and **both** are lost.
- Comments are whole lines only (`;` or `#`); there are no trailing comments, so `Font_Size=16 # big` has the literal value `16 # big`.
- Quotes are not stripped: `Font_Override="a.ttf"` looks for a filename including the quotes.
- Numbers go through `std::stof`, which takes the leading numeric prefix (`7.0s` → 7.0); an unparseable value costs that one key, not the file. An empty value reads as absent; a repeated key inside one file means last wins.
- Durations in `[overlay::appearance]` are **seconds** in the file, stored as milliseconds. Zero means "show nothing" — but the unlock sound still plays, since it is invoked separately.
- An unrecognised `PosAchievement` falls back to `top_right`, *not* to the `bot_right` default that applies when the key is absent — so a typo moves the notification rather than leaving it alone.
- The EXAMPLE ini's comment pointing at "GSE Settings/settings/fonts" is a doc typo; the real global folder is `%APPDATA%\GSE Saves\settings\`, with `fonts/` and `sounds/` beneath it.

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
- **achievement-overlay** (a sibling project, installed under the programs directory) — standalone WPF app that monitors `%appdata%/GSE Saves/` filesystem changes and shows toast-style notifications. No game process interaction. Survives anti-tamper. Its `GameCache` scans `gamesPaths` recursively for `steam_appid.txt`, detecting it in either the game root or inside `steam_settings/` (the `generate_emu_config` placement). The displayed game name is the first-level subfolder under the configured games root, so deeply-nested UE layouts render correctly (e.g. `<games-root>\Aphelion\...\Win64\steam_settings\` → "Aphelion").

## Other emulators write into GSE Saves too (Goldberg Uplay R2)

The `%appdata%\GSE Saves\<id>\achievements.json` layout is not exclusively GBE's. The **Goldberg uplay r2 Emulator** — Mr_Goldberg's open-source v0.0.2, continued as binary-only `GoldbergUplayR2-<MM-DD-YYYY>.7z` builds by cs.rin.ru user `demde` — can be pointed at it via two INI keys in `uplay_r2.ini` / `upc_r2.ini` (whichever loader pair the game uses):

- **`AchSavePath`** (added 2026-06-07) — absolute directory for `achievements.json`. `%APPDATA%` is **not** expanded by the emulator, so the path is written out with a literal username. The GSE Saves layout is therefore a *convention the user or setup script types in*, not something the emulator computes — and by that convention the folder is named with the **Steam** AppID (not the Ubisoft one) precisely so Steam-oriented trackers find it.
- **`AchKeyPrefix`** (added 2026-02-20) — the game only passes a numeric achievement id, so the emulator emits `<AchKeyPrefix>Ach_<id>` (e.g. `AFOP_Ach_7`). That happens to be the game's real Steam API name, which is why achievements "only work with games that also have achievements on Steam".

It also needs an `achievements_schema.json` next to the emulator DLL (required since 2026-03-28).

**Format divergences from GBE — both will break a strict reader:**

| | GBE | Goldberg Uplay R2 |
|---|---|---|
| `earned` | JSON bool (`true`/`false`) | **JSON number (`0`/`1`)** |
| `earned_time` | always present | added only on unlock |
| per-entry text | none (schema lives in `steam_settings/`) | carries `displayName` + `description` inline |
| icons | `achievement_images/` | **none anywhere** — `UPC_AchievementImageGet` is a stub in every open-source R2 variant |
| schema shape | JSON **array** of definitions | JSON **object** keyed by achievement name |

The unlock file starts as a byte-identical copy of `achievements_schema.json`, so it is fully self-describing — a reader can resolve display text from the save file alone, without locating the game folder. There is no `steam_appid.txt` anywhere: the game isn't running the Steam emulator at all, and the id appears only inside the `AchSavePath` value.

**Id-space collision:** Ubisoft/Uplay ids are small integers (`4` = AC2, `720` = AC Unity, `4740` = Avatar FoP) that fully overlap the Steam appid range. Anything keyed on a bare numeric id from a GSE Saves folder name can therefore mix up a Uplay and a Steam game — real enough that PSerban93/Achievements ships a `uplay-steam.json` mapping table for it. **Matching on the achievement name does not save you** where the schema's names are bare digits — see the survey below; two games installed on this machine name their achievements `1`..`29` and `01`..`54`.

Most of the above is forum-derived (cs.rin.ru thread `f=29&t=111722`) rather than read from source — treat the INI key names and "no icon field" as strong but unverified.

## Achievement API names: shapes, and the zero-padding mismatch

An emulator that is handed a bare integer achievement id has to turn it into the game's Steam API name. `AchKeyPrefix` concatenates a literal string ahead of the raw decimal id, so it can produce `AFOP_Ach_7` but **cannot zero-pad** — and a build configured with no prefix emits the bare `"1"`. Where the Steam schema spells that achievement `"001"`, an exact name match misses and the game gets no icon and no localised text. Padding is therefore the one part of such a name that cannot be fixed at the emulator's end; a reader has to bridge it.

Measured 2026-08-31 via `ISteamUserStats/GetSchemaForGame/v2` — 12,916 apps queried, 9,079 with achievements:

| | |
|---|---|
| AC Odyssey (812140) | 93 achievements, `001`..`093`, uniform width 3, never reaches 100. `001` = "This is Sparta!" |
| AC Origins (582160) | 67, `001`..`067` — the **only** other Ubisoft title like this |
| Ubisoft overall | of 80 published apps with achievements, 52 use `<Prefix>_Ach_<n>` **unpadded**. Padded numerics are a two-game quirk, not a Ubisoft convention |
| Anno 1800 (916440) | Ubisoft, numeric, **unpadded**, running to `215` — so the mismatch happens in both directions |
| all games | 224 entirely unpadded-numeric; 62 containing any padded name; widths 2, 3 **and** 4; 23 of them zero-based (so `0` must reach `00`/`000`) |
| CasinoRPG (658970) | width-3 padded, then runs `099` straight into `100`..`213` |
| Legendary Creatures 2 | `000`..`009`, then `0010` |
| Bulwark: Falconeer Chronicles | the only schema of 9,079 holding both a padded name **and** its unpadded twin (`01` and `1`) |

Consequences for anyone writing the match:

- **Do not reformat the key to a fixed width.** The last three rows break every such rule. Strip leading zeros from *both* sides instead and compare — that handles every width pair with no constant to choose.
- **Do not synthesise unpadded alias entries** into the parsed schema: it leaks phantom achievements into every other consumer, makes which entry answers a lookup depend on insertion order, and duplicates a real entry on that one schema which already has both spellings.
- **Try the exact match against the whole list first**, then the folded one. Otherwise a padded entry beats an exact one purely by appearing earlier in the file.
- **Fold as strings, never parse.** On .NET 10, `long.TryParse` with its default `NumberStyles.Integer` returns true for `"+1"` and `" 1 "`, fails outright past 19 digits, and via `double` equates `1234567890123456789` with `1234567890123456780`. Use `char.IsAsciiDigit`, not `char.IsDigit`, which accepts Arabic-Indic and fullwidth digits that a padding rule means nothing for. And never strip to the empty string — `"000".TrimStart('0')` is `""`, which then folds onto a nameless schema entry.
- **A folded match is an inference, not the schema naming the achievement.** Where the unlock file is self-describing, let the fold supply the icon and fill blank fields but not overwrite text the file carries: a wrong icon beside right text is visible, wrong text reads as correct.

Steam also redacts hidden achievements' `description`, so even a matched schema often supplies only `displayName` (31 of AC Odyssey's 93 are hidden) — the per-field fallback below still has work to do.

## Hidden achievement descriptions (Steam redacts; SteamDB via Firecrawl)

Steam's Web API `GetSchemaForGame` returns `description: ""` for `hidden=1` achievements (`displayName` is still present). The real text lives on SteamDB at `https://steamdb.info/app/<APPID>/stats/`, **but SteamDB is behind Cloudflare**. A plain `HttpClient`/curl gets **403 even with a valid `cf_clearance` cookie** — the cookie is bound to the browser's TLS/JA3 fingerprint (plus IP and a short-lived `__cf_bm` cookie), which a non-browser client can't reproduce; no User-Agent fixes it. SteamHunters and Completionist.me are also Cloudflare-blocked.

Working automated path: the **Firecrawl API** — a hosted scraper that solves Cloudflare and returns markdown:
- `POST https://api.firecrawl.dev/v1/scrape`, header `Authorization: Bearer <key>`, body `{"url": "...", "formats": ["markdown"], "onlyMainContent": true, "waitFor": 8000}`. The markdown is at `data.markdown` in the JSON response. (Firecrawl free tier is limited but plenty for one-off per-game configs.)
- **`waitFor` is mandatory, and its absence looks like success.** SteamDB renders the stats page's achievement table client-side, so a default scrape returns HTTP 200 with ~69 KB of genuine page markdown — app name, developer, app-info tables — in which the achievements section reads `## Achievements` followed by `Loading…`. Nothing signals an error: no Cloudflare challenge, no `success: false`, just zero achievements parsed, which reads as a parser bug. With `waitFor: 8000` the same page returns ~144 KB and every achievement (verified: Elden Ring, 42/42). Any "the page scraped but the parse found nothing" result on a JS-rendered site should be checked for this before the parser is suspected.
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
