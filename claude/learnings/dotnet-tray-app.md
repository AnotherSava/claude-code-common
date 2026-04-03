# .NET Windows Tray App Learnings

Practical patterns from building Windows system tray apps (url-cleaner, achievement-overlay) with .NET 10, WinForms tray lifecycle, WPF overlay windows, and filesystem-based detection. Everything here is general-purpose.

## Project Structure

Flat `src/` layout — no nested folders for small apps. Solution file uses modern `.slnx` format.

```
project-name.slnx
config/
  default.json              — default settings, copied to output as config.json
  deploy.env                — local install path (gitignored)
src/
  ProjectName.csproj
  Program.cs
  Logger.cs
  AppConfig.cs
  TrayApplicationContext.cs
  Assets/                   — embedded resources (icons, sounds)
tests/
  ProjectName.Tests.csproj
```

## .csproj Configuration

```xml
<OutputType>WinExe</OutputType>
<TargetFramework>net10.0-windows</TargetFramework>
<UseWindowsForms>true</UseWindowsForms>     <!-- NotifyIcon, tray lifecycle -->
<UseWPF>true</UseWPF>                       <!-- only if overlay windows needed -->
<Nullable>enable</Nullable>
<ImplicitUsings>enable</ImplicitUsings>
```

**WinForms + WPF hybrid**: When both are enabled, `System.Drawing` is auto-imported globally and conflicts with WPF types (Point, Color, Size, Pen, FontStyle). Fix with:
```xml
<Using Remove="System.Drawing" />
```
Then add `using System.Drawing;` explicitly only in files that need it (e.g. TrayApplicationContext).

**Embedded resources** use `LogicalName` for clean resource names:
```xml
<EmbeddedResource Include="Assets\icon.ico" LogicalName="ProjectName.icon.ico" />
```

**Ship config.json** by copying `config/default.json` to output:
```xml
<None Include="..\config\default.json" Link="config.json" CopyToOutputDirectory="PreserveNewest" CopyToPublishDirectory="PreserveNewest" />
```

## Entry Point (Program.cs)

```csharp
[STAThread]
static void Main()
{
    using var mutex = new Mutex(true, "AppName_SingleInstance", out var isNew);
    if (!isNew) return;

    Application.EnableVisualStyles();
    Application.SetCompatibleTextRenderingDefault(false);
    Application.SetHighDpiMode(HighDpiMode.SystemAware);

    // Only needed if using WPF overlay windows within WinForms lifecycle
    if (System.Windows.Application.Current == null)
        new System.Windows.Application { ShutdownMode = System.Windows.ShutdownMode.OnExplicitShutdown };

    Application.Run(new TrayApplicationContext());
}
```

- `[STAThread]` required for WinForms
- Named `Mutex` for single-instance enforcement
- `OnExplicitShutdown` prevents WPF from killing the app when overlay windows close

## Logging

Static `Logger` class — no callbacks, no DI, components call `Logger.Info/Warn/Error` directly. Simple `StreamWriter` with auto-flush. Initialize in `TrayApplicationContext` constructor, close in `Dispose`.

```csharp
public static class Logger
{
    private static StreamWriter? _writer;
    public static void Init() { _writer = new StreamWriter(logPath, append: false) { AutoFlush = true }; }
    public static void Info(string message) => Write("INFO", message);
    public static void Warn(string message) => Write("WARN", message);
    public static void Error(string message) => Write("ERROR", message);
    public static void Close() { _writer?.Dispose(); _writer = null; }
    private static void Write(string level, string message) =>
        _writer?.WriteLine($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [{level}] {message}");
}
```

**Why static over callbacks**: Eliminates 10+ `Action<string>` callback parameters threaded across component constructors. For a small single-process app, the simplicity outweighs testability concerns.

**Conventions**:
- Quote paths in log messages with single quotes for readability in log viewers
- Use `[WARN]` for config issues that degrade functionality, `[ERROR]` for fatal startup issues
- Log the full config on startup for diagnostics

**Version logging**: Use `AssemblyInformationalVersionAttribute` which is set by `-p:Version=` during CI release builds. Strip the `+commitHash` suffix. Show `dev version` for local builds:

```csharp
var infoVersion = typeof(T).Assembly
    .GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion?.Split('+')[0];
var versionLabel = infoVersion != null && infoVersion != "1.0.0" ? $"v{infoVersion}" : "dev version";
```

## AppConfig Pattern

**Single source of truth**: `config/default.json` ships as `config.json` next to the exe. No embedded defaults, no merging, no auto-creation. `SettingsData` class has no hardcoded defaults — all properties default to zero/empty.

**Load behavior**:
- File exists → deserialize and validate
- File missing → throw `FileNotFoundException` (app exits with error dialog)
- File has invalid JSON → throw `JsonException` (app exits with error dialog)
- File has invalid values → throw `InvalidOperationException` (app exits with error dialog)

**Validation**: Check required fields after deserialization. String fields: non-empty. Int fields: positive. Directory fields: must exist on disk. Collect all errors and report together:

```csharp
private static void Validate(SettingsData settings)
{
    var errors = new List<string>();
    if (string.IsNullOrWhiteSpace(settings.SomePath)) errors.Add("'somePath' is missing or empty");
    else if (!Directory.Exists(ExpandEnvironmentVariables(settings.SomePath)))
        errors.Add("'somePath' directory does not exist");
    if (settings.SomeCount <= 0) errors.Add("'someCount' is missing or invalid");
    if (errors.Count > 0)
        throw new InvalidOperationException("Invalid config: " + string.Join("\n", errors));
}
```

**Note on directory validation in tests**: Directory existence checks in `Validate()` break tests that use fake paths. Move directory checks to `TrayApplicationContext` (after config loads, before components start) so tests can use `AppConfig` with nonexistent paths. Or ensure tests create the directories they reference.

**Hot-reload**: Check `File.GetLastWriteTimeUtc()` on property access. Double-checked locking. On malformed/locked file, keep last good config without advancing the timestamp (so it'll retry).

**UpdateConfigValue**: Read-modify-write with `Dictionary<string, JsonElement>`. Log warnings on failure (IOException, JsonException) — the setting won't persist but in-memory state still updates.

**Config file naming**: `config.json` next to the exe. CamelCase in JSON via `JsonNamingPolicy.CamelCase`.

**Registry auto-start**:
```csharp
const string RunKey = @"SOFTWARE\Microsoft\Windows\CurrentVersion\Run";
Registry.CurrentUser.OpenSubKey(RunKey, writable: true);
key.SetValue(AppName, $"\"{exePath}\"");
```

## Error Dialogs

Use `TaskDialog` (not `MessageBox`) for startup errors — supports expandable details section showing the log file content:

```csharp
var page = new TaskDialogPage
{
    Heading = "Config file is invalid",        // High-level reason
    Text = "'gamesPaths' is missing or empty",  // Specific detail
    Icon = TaskDialogIcon.Error,
    Caption = "App Name",
    Buttons = { TaskDialogButton.OK }
};
if (!string.IsNullOrEmpty(logContent))
    page.Expander = new TaskDialogExpander
    {
        Text = logContent,
        CollapsedButtonText = "Details",
        ExpandedButtonText = "Details",
        Position = TaskDialogExpanderPosition.AfterFootnote  // Separator line above details
    };
TaskDialog.ShowDialog(page);
```

**Pattern**: Log the detailed error first (`Logger.Error`), close the logger (`Logger.Close()`), read the log file, show dialog with expandable log, then `Environment.Exit(1)`. Extract into a `ShowConfigError(heading, detail)` helper to reuse across config validation, path checks, and game detection.

**Dialog text guidelines**: Heading is the category (no period). Detail is the specific issue. Don't put full file paths in the dialog — those go in the log. Separate multiple errors with newlines.

## TrayApplicationContext Pattern

Inherits `ApplicationContext`. Manages `NotifyIcon` with `ContextMenuStrip`.

**Early exit fields**: Constructor has early `return` paths (config error, missing paths). Fields assigned after those paths use `= null!` to suppress CS8618 nullable warnings — the process exits before they'd be accessed.

**Menu item patterns**:
- **Checkbox with persist**: `CheckOnClick = true`, `CheckedChanged` → `UpdateConfigValue`
- **Checkbox session-only**: `CheckOnClick = true`, `CheckedChanged` → set in-memory flag
- **Checkbox with registry**: `CheckedChanged` → `SetStartWithWindows()`, revert on exception
- **Open config**: `Process.Start("explorer.exe", $"/select,\"{path}\"")`
- **Shortcut display**: `ShortcutKeyDisplayString` property for right-aligned shortcut text

**Icon management**: Active icon + grayscale paused variant. Pixel-by-pixel luminance conversion (0.299R + 0.587G + 0.114B). `Icon.FromHandle` doesn't own the HICON — must `DestroyIcon` via P/Invoke after cloning.

**Dispose order**: Hide tray icon → dispose tray → dispose components → dispose icons → close logger.

## WPF Overlay Windows

**Transparent topmost borderless window**:
```xml
WindowStyle="None" AllowsTransparency="True" Background="Transparent"
Topmost="True" ShowInTaskbar="False" ShowActivated="False"
SizeToContent="WidthAndHeight"
```

**Avoid shadowing Window.Show()**: Name custom show methods `ShowNotification()`, `ShowRecent()`, etc. — not `Show()` which hides the base `Window.Show()`.

**Proportional sizing** — all dimensions relative to screen, not fixed pixels:
- Window width: 15% of screen width (min 250px)
- Icon size: 25% of window width (min 32px)
- Margin from edge: 2% of smaller screen dimension
- Slide distance: 1.5% of screen height

**Animation**: `TranslateTransform` for slide, `Opacity` for fade. CubicEase for slide-in, linear for fade. Use `DispatcherTimer` for hold duration.

**Multi-monitor with mixed DPI**: WPF positions windows using the primary monitor's DPI as coordinate basis. `Screen.WorkingArea` returns physical pixels. Convert all coordinates by dividing by primary monitor's DPI scale:
```csharp
var primaryDpiScale = Screen.PrimaryScreen!.Bounds.Height / SystemParameters.PrimaryScreenHeight;
return new Rect(wa.Left / primaryDpiScale, wa.Top / primaryDpiScale, ...);
```

**Measurement before show**: `window.Measure()` before the window is in the visual tree gives unreliable height. Use `Dispatcher.BeginInvoke` at `DispatcherPriority.Loaded` after `Show()` to read `ActualHeight` and correct position.

**Cascade display**: When showing multiple windows sequentially, track the active `DispatcherTimer` and stop it in `Dismiss()` to prevent orphaned windows appearing after dismiss.

## Global Hotkey (Win32)

```csharp
RegisterHotKey(hWnd, id, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, vk);
```

- Hidden `NativeWindow` subclass receives `WM_HOTKEY` (0x0312) via `WndProc`
- Parse hotkey strings like "Ctrl+Shift+H" → modifiers + Keys enum
- Validate `vk != 0` before calling `RegisterHotKey` (invalid key names parse to 0)
- `MOD_NOREPEAT` prevents auto-repeat spam
- Registration can fail if key combo is taken — degrade gracefully (show menu item without shortcut)
- For toggle actions, add debounce guard (ignore within 1 second of show) to prevent WM_HOTKEY re-entrancy during message pump processing

## FileSystemWatcher

- Set `InternalBufferSize = 32768` (default 8192 can overflow under load)
- Subscribe to `Error` event for overflow detection
- Debounce change events (100ms) — FSW fires multiple times per write
- Use `ConcurrentDictionary<string, CancellationTokenSource>` for per-file debounce
- Check `File.GetLastWriteTimeUtc` to skip truly unchanged files
- Retry on `IOException` (file locked by game writing) with async delay

## Testing

xUnit with `Microsoft.NET.Test.Sdk`. Test project mirrors main project's `UseWindowsForms`/`UseWPF` settings. Must add `using Xunit;` explicitly (not auto-imported).

**Test config pattern**: Internal constructor on `AppConfig` accepting custom settings path. Tests create temp directories for all paths (including `gseSavesPath`) — never rely on machine-specific directories like `%appdata%\GSE Saves` existing.

**Test helpers**: Builder methods with optional named parameters for readable test config construction.

## Deploy

Global deploy script at `~/.claude/skills/deploy/scripts/deploy.sh`. Reads `config/deploy.env` for `INSTALL_DIR`. Script: stop process → clean publish dir → `dotnet publish` → clean install dir → copy → optionally launch → verify running.

Each project has a `scripts/deploy.sh` (gitignored) that delegates to the global script. A bash function in `~/.bashrc` enables `deploy` (or `deploy 0` to skip launch) from any project:

```bash
deploy() { if [ -f scripts/deploy.sh ]; then bash scripts/deploy.sh "$@"; else echo "No scripts/deploy.sh in current directory"; fi; }
```

Deploy target is flat files only (`rm -f`, not `rm -rf`) — embed all resources to avoid subdirectories in output.

## .gitignore

```
bin/
obj/
publish/
.claude/settings.local.json
docs/*
!docs/plans/
!docs/screenshots/
config/deploy.env    # machine-specific install path (also in global gitignore)
scripts/             # dev/test scripts
```

## GitHub Actions CI/CD

Windows-only projects (`net10.0-windows` with WinForms/WPF) require `windows-latest` runner. Workflow at `.github/workflows/build.yml`:

**Build/test on every push and PR:**
```yaml
runs-on: windows-latest
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-dotnet@v4
    with: { dotnet-version: 10.x }
  - run: dotnet restore
  - run: dotnet build -c Release --no-restore
  - run: dotnet test tests/ -c Release --no-restore
```

**Release on version tags** (`v*`): Publish self-contained (single exe) and framework-dependent variants, package as zips, create GitHub Release with `gh release create --generate-notes`. The release job runs on `ubuntu-latest` (just downloads artifacts and calls `gh`), only the build job needs Windows.

**Version from tag**: Strip `v` prefix from tag name:
```yaml
- if: startsWith(github.ref, 'refs/tags/v')
  shell: bash
  run: echo "VERSION=${GITHUB_REF_NAME#v}" >> "$GITHUB_ENV"
- run: dotnet publish src/ -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:Version=${{ env.VERSION }}
```

## Multi-size ICO Files

Windows tray icons need multiple sizes: 16x16 (tray), 32x32 (alt-tab), 48x48 (taskbar large), 256x256 (explorer). Generate with Pillow:

```python
icons = [img.resize(s, Image.LANCZOS) for s in [(16,16), (32,32), (48,48), (256,256)]]
icons[0].save("icon.ico", format="ICO", sizes=sizes, append_images=icons[1:])
```

Hand-crafted pixel art at small sizes looks better than downscaled from large images. Use `Image.LANCZOS` for quality downscaling.

## Achievement Icon Resolution

Steam/GBE achievement icons are 256x256 JPEG. Icon paths in `steam_settings/achievements.json` are relative to `steam_settings/` (e.g. `"icon": "img/abc123.jpg"`). Resolve with path traversal protection:

```csharp
var metaDirFull = Path.GetFullPath(metadataDir) + Path.DirectorySeparatorChar;
var exactPath = Path.GetFullPath(Path.Combine(metadataDir, iconName));
if (exactPath.StartsWith(metaDirFull, OrdinalIgnoreCase) && File.Exists(exactPath))
    return exactPath;
```
