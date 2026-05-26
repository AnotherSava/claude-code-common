---
name: build
description: Configure build script and run it
allowed-tools: Bash(bash ~/.claude/skills/build/scripts/build.sh), Bash(build), Bash(echo *), Bash(test *), Bash(ls *), Bash(mkdir *), Bash(find *), Bash(grep *), AskUserQuestion, Write(scripts/build.sh), Write(.github/workflows/build.yml), Edit(.gitignore), Read(.gitignore), Edit(~/.bashrc), Read(~/.bashrc), Read(package.json), Read(.nvmrc), Read(global.json)
---

See `~/.claude/learnings/shell-environment.md` for the expected bash functions and verification checklist.

## Context
- Build function in bashrc: !`grep -c "build()" ~/.bashrc 2>/dev/null || echo 0`
- Wrapper script exists: !`test -f scripts/build.sh && echo yes || echo no`
- Scripts in gitignore: !`grep -cx 'scripts/' .gitignore 2>/dev/null || echo 0`
- GitHub workflow: !`ls .github/workflows/*.yml 2>/dev/null || echo none`

## 1. Check prerequisites

1. If **Build function** is 0, append the function to `~/.bashrc`:
   ```bash
   build() { if [ -f scripts/build.sh ]; then bash scripts/build.sh "$@"; else echo "No scripts/build.sh in current directory"; fi; }
   ```

## 2. Set up quick build shortcut

1. If **Wrapper script exists** is no, create `scripts/build.sh`:
   ```bash
   #!/bin/bash
   bash ~/.claude/skills/build/scripts/build.sh "$@"
   ```
2. If **Scripts in gitignore** is 0, append to `.gitignore`:
   ```
   # Local convenience scripts (not committed)
   scripts/
   ```

## 3. Configure GitHub Actions CI (optional)

If **GitHub workflow** is `none`:

1. Ask the user: "No GitHub Actions workflow found. Set up CI for push/PR builds?"
2. If declined, skip to step 4.
3. Detect project type and parameters (see below).
4. Generate the workflow, show it to the user for approval.
5. On approval: `mkdir -p .github/workflows`, then write `.github/workflows/build.yml`.

### Project type detection

| Check | How | Type |
|---|---|---|
| `test -d src-tauri` | directory exists | **Tauri** |
| `test -f package.json` | file exists (and not Tauri) | **npm** |
| `find . -maxdepth 2 -name '*.csproj'` | csproj found | **dotnet** |

### Parameter detection

**npm:**
- **Node version**: if `.nvmrc` exists → use `node-version-file: .nvmrc` (stays in sync). Else read `engines.node` from `package.json` → use minimum major. Else default `24` (current active LTS).
- **Lint**: include `npm run lint` step only if `package.json` has a `scripts.lint` entry.
- **Test**: include `npm test` step only if `package.json` has a `scripts.test` that is not the default `echo "Error: no test specified" && exit 1`.

**dotnet:**
- **.NET version**: `global.json` `sdk.version` → `{major}.x`. Else parse `TargetFramework` from csproj (`net9.0` → `9.x`). Default `9.x`.
- **Runner**: if csproj contains `<RuntimeIdentifier>win-` or `<UseWPF>` or `<UseWindowsForms>` → `windows-latest`. Else `ubuntu-latest`.
- **Test**: include test step only if `tests/` directory exists.

**Tauri:**
- **Node version**: same logic as npm.
- **Runner**: matrix build — `windows-latest` and `macos-latest`. Each runner uses its native Rust target (x86_64 on Windows, aarch64 on macOS ARM runners).
- **Rust cache**: always include `Swatinem/rust-cache@v2` with `workspaces: src-tauri -> target`.

### Reference workflows

Generate `.github/workflows/build.yml` following these patterns. Omit commented lines that don't apply; do not leave comments in the output.

**npm** (reference: bga-assistant):
```yaml
name: Build

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version-file: .nvmrc  # or node-version: '24' if no .nvmrc
          cache: npm

      - run: npm ci

      - run: npm run lint    # omit if no lint script

      - run: npm run build

      - run: npm test        # omit if no real test script
```

**dotnet** (reference: crop-stage):
```yaml
name: Build

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest  # or windows-latest for Windows-only targets
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-dotnet@v4
        with:
          dotnet-version: '9.x'

      - run: dotnet restore

      - run: dotnet build -c Release --no-restore

      - run: dotnet test tests/ -c Release --no-restore  # omit if no tests/ dir
```

**Tauri** (reference: tauri-dashboard):
```yaml
name: Build

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    strategy:
      matrix:
        os: [windows-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '24'  # or node-version-file: .nvmrc
          cache: npm

      - uses: dtolnay/rust-toolchain@stable

      - uses: Swatinem/rust-cache@v2
        with:
          workspaces: src-tauri -> target

      - run: npm ci

      - run: cargo test --manifest-path src-tauri/Cargo.toml --lib

      - run: npm run build
```

## 4. Build

If step 1 or 2 made changes, tell the user:
> The `build` shortcut has been configured. **Restart Claude Code** for `! build` to work — the shell reads `~/.bashrc` only at startup, so new functions aren't available until the next session.
>
> For now, running the build directly:

Run the build script directly (bypassing the shell function):
```
bash ~/.claude/skills/build/scripts/build.sh
```

Report the output to the user. If it fails, analyze the error and suggest a fix. On success, remind the user to restart Claude Code if they haven't already, then `! build` will work.
