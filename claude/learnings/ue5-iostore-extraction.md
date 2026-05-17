# Extracting UE5 IoStore Containers (.utoc/.ucas)

UE5 ships content in IoStore containers (`.utoc` table-of-contents + `.ucas` data + a tiny `.pak` stub) instead of legacy `.pak` archives. Standard `.pak` extractors won't work. Two CLI tools by trumank handle this cleanly:

## Tools

- **retoc** — https://github.com/trumank/retoc — IoStore extractor, ~7MB Windows binary
- **repak** — https://github.com/trumank/repak — legacy `.pak` extractor, ~5MB

Prebuilt Windows binaries on GitHub releases (e.g. `retoc_cli-x86_64-pc-windows-msvc.zip`, `repak_cli-x86_64-pc-windows-msvc.zip`). No .NET / Python / build chain needed.

Alternative: **FModel** (https://github.com/4sval/FModel) is the GUI standard — built on CUE4Parse (also by 4sval). More battle-tested across edge cases than retoc, but GUI-only. For headless CLI work, retoc is the fit. Forking FModel for CLI is overkill — its logic is heavily UI-coupled, and CUE4Parse is already a programmatic API; a 30-line C# console wrapping CUE4Parse is the proportional version.

## Common operations

### Find a file without extracting (cheap)

```bash
retoc.exe manifest <path>.utoc
# Writes pakstore.json (~1-3MB JSON index) to current dir with all internal paths.
grep -oE '"filename":"[^"]*\.locres"' pakstore.json
```

`retoc list` shows chunk hashes + types but NOT paths — use `manifest` for the path index.

### Extract everything raw

```bash
retoc.exe unpack <path>.utoc <output-dir>
```

**Beware:** extracts ALL chunks (textures, models, audio). A typical AAA UE5 game's full unpack is 30–50+ GB. Clean up after with `rm -rf` — don't leave it in `/tmp`.

### Extract with conversion to legacy `.uasset` format

```bash
retoc.exe to-legacy --filter ".locres" <path>.utoc <output-dir>
```

`to-legacy` typically requires the global `ScriptObjects` chunk; without it, fails with `does not contain FIoChunkId { chunk_id: "...", chunk_type: ScriptObjects }`. Use `unpack` (raw) when this fails.

`--filter` only works with `to-legacy`, NOT `unpack`. For raw `unpack`, run on the full archive then prune locally.

### Multi-chunk archives

Games typically split content across `pakchunk0` (engine + base), `pakchunk1`, `pakchunk2` (main content), `pakchunk3` (DLC/extras). Each `.utoc` is independent — run `manifest` on each to find the right one before unpacking.

## What's actually inside `.uasset` files

For Steam-integrated UE5 games, achievement-related uassets (`DA_ACH_*.uasset`, etc.) are typically **300-byte stubs** — only the icon path, hidden flag, and asset ID. **Display strings (achievement names, descriptions) are NOT embedded**; the game fetches them from Steam at runtime via `ISteamUserStats::GetAchievementDisplayAttribute(name, "name"|"desc")`. Same pattern likely holds for any platform where the achievement text comes from a backend (Xbox Live, PSN, EOS).

If you need verbatim achievement text and the game's localization isn't using `.locres` files, the source is Steam itself (SteamDB or `Steam/appcache/stats/UserGameStatsSchema_<APPID>.bin`) — not the game's pak.

Verified empirically with Aphelion (App ID 1966410): extracted all 4 IoStore chunks (~50GB), searched in ASCII and UTF-16 for both the visible achievement names ("The Wreck", "Complete Chapter 1") and hidden ones ("Whisperstep", "Cliffhanger") — **none of them present anywhere** in the unpacked output. Strings live exclusively in Steam's backend.

## Chunk types in `retoc list` output

- `ExportBundleData` — primary asset data (.uasset payloads)
- `BulkData` — separately-streamed asset bodies (textures, audio)
- `ShaderCode` — compiled shaders

## Localization notes

UE5 games may use one of two localization systems:

1. **`.locres` files** (compiled localization tables) — the traditional path. Extract with `unpack`, then parse with `UnrealLocres` (https://github.com/akintos/UnrealLocres) → JSON/CSV.

2. **`.uasset` string tables** (e.g. files prefixed `STB_*.uasset`) — newer pattern. Strings are inside serialized UE asset format, not extractable as plaintext. Need a full asset parser (CUE4Parse, FModel) to read them.

When `manifest` shows no `.locres` paths but plenty of `STB_*.uasset` files, you're in the second case — strings exist but extraction is harder than `unpack`+grep.

## Worked example: Aphelion

```bash
# Find achievement assets without extracting
retoc.exe manifest C:/Games/Aphelion/Aphelion/PIO/Content/Paks/pakchunk2-Windows.utoc
grep -oE '"filename":"[^"]*Achievements/[^"]*"' pakstore.json | sort -u

# Returns: DA_ACH_END_CHAPTER01.uasset ... DA_ACH_NEM_NOALERT.uasset (30 files)

# Raw extract chunk2 (only chunk with Achievements/ paths)
retoc.exe unpack C:/Games/Aphelion/Aphelion/PIO/Content/Paks/pakchunk2-Windows.utoc /tmp/extract/
# 12k files, ~20GB

# Each DA_ACH_*.uasset is 300-340 bytes, contains only the asset path string and metadata
```

Conclusion for that game: useless for getting achievement text; SteamDB scrape via firecrawl was the working source.
