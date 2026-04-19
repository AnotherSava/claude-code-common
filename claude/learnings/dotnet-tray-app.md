# .NET Windows Tray App Learnings

Practical patterns from building Windows system tray apps (url-cleaner, achievement-overlay) with .NET 10, WinForms tray lifecycle, WPF overlay windows, and filesystem-based detection. Everything here is general-purpose.

## Project Structure

Flat `src/` layout for small single-feature apps — no nested folders. Solution file uses modern `.slnx` format.

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

**Multi-feature apps**: once you have two+ independent features (each with its own windows, coordinators, state), group per-feature files into `src/Features/<FeatureName>/`. Keep shared infrastructure (AppConfig, Logger, GlobalHotkey, AppUtilities, TrayApplicationContext, Program) at `src/` root. Each feature exposes a single coordinator class (`<FeatureName>Feature.cs`) that the tray context wires in. This keeps grep-finding easy and scales without restructuring when a new feature lands.

**GlobalHotkey digit parsing gotcha**: `Enum.TryParse<Keys>("0")` succeeds as `Keys.None` (integer 0), not `Keys.D0` (48). When parsing hotkey strings like `Ctrl+Shift+0`, check `char.IsDigit` **before** `Enum.TryParse`, and map digit chars explicitly to `Keys.D0 + digit`.

**`AllowsTransparency="True"` overlay is a perf trap**: A per-pixel-transparent topmost overlay (for things like a hollow frame or a grid overlay where only some pixels are opaque) creates a layered window (`WS_EX_LAYERED`) that DWM participates in composition for. A ~1MP layered window causes noticeable UI lag on **every topmost Z-order disturbance** — which includes focus changes between fields in a sibling topmost dialog. Symptoms: tabbing between adjacent TextBoxes in the tool dialog feels sluggish even though the commit path is a no-op.

For hollow-rectangle overlays (frames, selection boxes, borders), use **4 thin opaque borderless topmost windows** (one per edge) instead of one transparent one. Each edge window is ~2px thick, no `AllowsTransparency`, solid `Background`. Click-through via `WS_EX_TRANSPARENT | WS_EX_NOACTIVATE` P/Invoke on `SourceInitialized`. Matches what AutoHotkey does for the same problem and is orders of magnitude cheaper. Reserve `AllowsTransparency="True"` for cases where you genuinely need per-pixel alpha (semi-transparent content, anti-aliased curves over arbitrary backgrounds).

**Dialog `SizeToContent="WidthAndHeight"` with TextBox focus visuals**: each LostFocus can nudge measured size by a sub-pixel, triggering a window resize and any `SizeChanged` handlers. If a `SizeChanged` handler does anything non-trivial (e.g. repositions another window), it fires on every field-to-field tab. Prefer explicit `Width`/`Height` for dialogs whose content shape doesn't actually change. Only use `SizeToContent` if you truly need auto-sizing.

**State-save on UI thread**: `File.WriteAllText` to any path can take 50-500ms under Windows Defender real-time scan. If the save is triggered by UI events (field commit, etc.), route it off the UI thread. A `ContinueWith` chain on `Task.CompletedTask` guarded by a small lock gives you ordered async writes without the thread-pool queue-race problems of bare `Task.Run`.

**Mysterious TextBox focus lag = third-party input hooks**: If a WPF (or WinForms) TextBox feels noticeably laggy on focus changes — click→focus taking 100-200ms with no visible cost in any event handler — suspect a global input assistant installed on the user's system. Known offenders: **Grammarly**, other writing assistants, some password managers, some IMEs. They subclass edit controls globally and run their own analysis before the focus event reaches user code, which is invisible to any instrumentation you add.

Symptoms that point at this (rather than at something in your code):
- `PreviewMouseDown` → `LostFocus`/`GotFocus` completes in <5ms in your logs, but the user still perceives lag
- "click→idle" round-trip (queue a callback at `DispatcherPriority.ApplicationIdle`) is variable — sometimes 3ms, sometimes 200ms
- WPF render tier is 2 (full HW acceleration), so rendering isn't at fault
- Microsoft's own Q&A has [the exact same symptom](https://learn.microsoft.com/en-us/answers/questions/1051205/how-to-fix-the-bad-performance-of-the-wpf-textbox) reported with lag on "some machines but not others"

Before rewriting UI or blaming WPF, **ask the user what they have installed that hooks into text input**. Grammarly is the single most common culprit. Pausing/quitting it should instantly make the dialog snappy. Also set `SpellCheck.IsEnabled="False"` explicitly on TextBoxes for defense (default is false but explicit shuts off any code path that touches `HKCU\Software\Microsoft\Spelling\Dictionaries` — stale entries there cause a separate but related slowdown).

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

**`WS_EX_NOACTIVATE` topmost windows get demoted** — they never participate in foreground activation, so over time (new windows opening, other apps gaining focus) they can drop below normal windows even though they're flagged topmost. Setting `Topmost=true` once at creation isn't enough. Re-assert explicitly via `SetWindowPos(hwnd, HWND_TOPMOST, ...)` on `Show()` and on every geometry update (SetWindowPos is cheap; drag updates happen at frame rate but don't cause noticeable overhead). `HWND_TOPMOST = new IntPtr(-1)`. Use `SWP_NOACTIVATE` so the re-assertion doesn't steal focus.

**Avoid shadowing Window.Show()**: Name custom show methods `ShowNotification()`, `ShowRecent()`, etc. — not `Show()` which hides the base `Window.Show()`.

**Proportional sizing** — all dimensions relative to screen, not fixed pixels:
- Window width: 15% of screen width (min 250px)
- Icon size: 25% of window width (min 32px)
- Margin from edge: 2% of smaller screen dimension
- Slide distance: 1.5% of screen height

**Animation**: `TranslateTransform` for slide, `Opacity` for fade. CubicEase for slide-in, linear for fade. Use `DispatcherTimer` for hold duration.

**Multi-monitor with mixed DPI — fundamental WPF limitation first**: WPF renders a window at **one** DPI at a time. When a window crosses a mixed-DPI boundary, it renders at one monitor's DPI and DWM bitmap-stretches the overflow on the other monitor. There is no mode in which parts of the same window render at different DPIs — not in SystemAware, not in PerMonitorV2, not in DpiUnaware. Accept that some kind of visual discontinuity at the boundary is unavoidable and pick the least-bad tradeoff; don't promise users "gradual per-monitor rendering" because WPF can't deliver it.

**Picking the DPI mode**:
- `SystemAware`: app uses primary DPI everywhere, DWM virtualizes secondaries. Works for notification-style apps that live on one monitor. *Breaks* when you have a frame window following a dialog window — DWM virtualization makes the dialog's logical rect stop matching its visible rect on non-primary monitors, so the frame visibly detaches.
- `PerMonitorV2`: each window uses its current monitor's DPI, content stays crisp. A window's physical size changes when it crosses the boundary (WPF auto-handles `WM_DPICHANGED` by preserving DIPs → new physical size). This is what File Explorer does. Right default for anything beyond a single notification popup.

**Fighting WPF's DPI events creates oscillation**: Any handler that restores a window's position after `WM_DPICHANGED` can put the window back on the previous monitor, causing the OS to fire `WM_DPICHANGED` again → infinite loop. Symptom: window flickers between two sizes when its center hovers near the boundary. Corollary: only restore **size** in a DPI handler, never position; and even for size, prefer swallowing the message outright over overriding after the fact.

**Swallow `WM_DPICHANGED` for fixed-physical-size decorative windows**: For overlays whose physical pixel size must stay constant (screenshot frames, rulers, crosshairs) and whose content is DPI-insensitive (solid colors, simple shapes), swallow the message via an `HwndSource` hook:
```csharp
HwndSource.FromHwnd(hwnd)?.AddHook((IntPtr h, int msg, IntPtr wp, IntPtr lp, ref bool handled) =>
{
    const int WM_DPICHANGED = 0x02E0;
    if (msg == WM_DPICHANGED) handled = true;
    return IntPtr.Zero;
});
```
WPF then stays at its original render DPI for the window's whole lifetime. DWM bitmap-stretches on other monitors, which is imperceptible for solid colors. No oscillation since nothing triggers re-evaluation of the window's monitor.

**DPI source matters: WPF's render DPI vs OS monitor DPI**: `VisualTreeHelper.GetDpi(window)` returns **WPF's** current render DPI for the window. `MonitorFromWindow` + `GetDpiForMonitor` returns the **OS's** view of the window's current monitor DPI. Normally these agree. They diverge when you've swallowed `WM_DPICHANGED` — WPF's is stuck at creation-time, OS's reflects reality. When converting physical pixels to DIPs for content (BorderThickness, StrokeThickness, child positions), use **WPF's** — otherwise DIPs × WPF's stale render DPI produces physical pixels thicker than intended, and a border drawn inside-the-rect bleeds into whatever's inside (visible in screenshots).

**Positioning in physical pixels**: In PerMonitorV2, `SetWindowPos` coordinates are physical virtual-screen pixels regardless of any window's DPI state — use it when you need pixel-exact placement across monitors. Force HWND creation with `WindowInteropHelper.EnsureHandle()` so `SetWindowPos` can place the window before `Show()` (avoids a flash at whatever `Left`/`Top` you initialized the Window with).

**Don't over-engineer layered vs opaque windows**: An old instinct to avoid `AllowsTransparency="True"` for perf ("DWM recomposites on every topmost-Z disturbance") is real but usually negligible. A single transparent topmost window with a `Border` + a couple of `Line` shapes is simpler, more correct, and fast enough — don't break it into four opaque edge windows just to avoid a layered surface. Go 4-opaque only if profiling shows actual DWM cost.

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

## WPF Gotchas (from the screen-tools port)

**WPF dialog shown modelessly from WinForms `Application.Run` needs `ElementHost.EnableModelessKeyboardInterop` — or text input silently fails**: This is the single most disorienting bug in the WinForms-tray + WPF-overlay hybrid. Symptoms: a WPF dialog opens fine, textboxes accept focus (`GotKeyboardFocus` fires), `PreviewKeyDown` and `KeyDown` fire on every key, but `PreviewTextInput`/`TextInput` *never* fire, so letters and digits never appear in textboxes. Backspace and Delete still work because TextBox handles them in KeyDown without needing TextInput. Esc, Tab, arrow keys also work. It looks like a keyboard hook — Grammarly, TSF/`ctfmon`, IME, password manager — but it isn't. Killing every suspect process changes nothing. Disabling TSF via `InputMethod.IsInputMethodEnabled="False"` on the textbox style changes nothing.

The actual cause: WPF's input system requires a WinForms `IMessageFilter` bridge to receive WPF-bound keyboard messages from the WinForms message pump. WPF's `Application.Run` installs this bridge automatically; WinForms's `Application.Run` does not. Without it, `WM_KEYDOWN` reaches the WPF window's `WndProc` (so `KeyDown` fires), but `WM_CHAR` is not converted into a WPF `TextInput` event.

Fix — call **once per WPF window**, after `_dialog.Show()`:

```csharp
System.Windows.Forms.Integration.ElementHost.EnableModelessKeyboardInterop(_dialog);
```

The API name is misleading (it sounds WinForms-only); it's the canonical fix for any WPF Window opened modelessly from a WinForms host. Diagnostic to confirm: log `WidthBox.PreviewKeyDown` and `WidthBox.PreviewTextInput`. If KeyDown fires for letters but PreviewTextInput never does, this is the bug — don't go down the third-party-hook rabbit hole.

**ESC (or other system-level shortcuts) — `RegisterHotKey` if you need to catch them outside the focused window**: Once `EnableModelessKeyboardInterop` is wired up, `PreviewKeyDown` on the dialog catches Esc fine when the dialog has keyboard focus. Use Win32 `RegisterHotKey` only when you need the shortcut to fire even when something *else* (a child dialog like a folder picker, another app entirely) has focus. Trade-off: hotkey is captured system-wide while registered — so unregister it when modal child dialogs open (e.g. before `OpenFileDialog.ShowDialog()`) so the picker can dismiss with Esc, and re-register after.

**Dialog `ActualWidth` / `ActualHeight` is 0 before first render**: When computing initial window placement, `_dialog.ActualWidth` returns 0 until after the first layout pass. Options in order of preference:
1. Set explicit `Width`/`Height` in XAML and read them directly.
2. With `SizeToContent`, cache via `GetDialogWidth()` helper: prefer `ActualWidth` when populated, else `Measure(PositiveInfinity).DesiredSize.Width`, with a sensible fallback.
Beware of `Window.Show()` firing `LocationChanged` immediately — if handlers use `ActualWidth`, they get 0 and compute wrong positions (visible as "dialog ends up stacked wrong on first launch, correct after drag").

**`OpenFolderDialog` hides files by design**: `Microsoft.Win32.OpenFolderDialog` (.NET 8+) wraps `IFileDialog` with `FOS_PICKFOLDERS`, which inherently hides files. If users want to see files as context while picking a folder, fall back to `OpenFileDialog` with `CheckFileExists=false`, `ValidateNames=false`, and a placeholder `FileName`. Strip the filename on return: `Path.GetDirectoryName(dlg.FileName)`. Less clean UX but shows files.

**Animated `SolidColorBrush` can't be `Freeze()`d**: If you need to animate a brush's `Color` property (e.g., screenshot-taken flash), do NOT call `.Freeze()`. Frozen brushes are immutable; `BeginAnimation` silently does nothing. The animation also requires one brush shared across all elements that should pulse together — changing `Color` on the shared brush updates all bound `Background`s in one pass.

**Capture-without-hide for tools with UI outside the capture rect**: If your overlay UI (frame borders, dialog) is geometrically *outside* the rectangle being captured, skip the traditional hide-sleep-capture-show dance entirely. Just capture. Flash the border via a `ColorAnimation` for visual confirmation. Much better UX than the flicker of hide/show.

**`WindowStyle="None"` + drag-anywhere**: For frameless tool windows, implement drag via `MouseLeftButtonDown` on the Window:
```csharp
MouseLeftButtonDown += (s, e) => {
    if (e.OriginalSource is TextBlock or Border or Grid or Window) DragMove();
};
```
Guard on `OriginalSource` type so clicks on `TextBox`/`Button` aren't hijacked for drag. Labels (`TextBlock`), background `Border`, `Grid`, and the `Window` itself become drag regions; interactive controls work normally.

**Bottom-pivot resize for sizing-frame tools**: When the user adjusts frame dimensions and the dialog is anchored to a specific corner, make dimension changes pivot at that corner. E.g., dialog flush below frame → compute `interiorTop = dialog.Top - interiorHeight - borderThickness` on every sync. Width changes pivot at left, height changes pivot at bottom. This keeps the dialog's tether point stable during resize.

**WPF `KeyEventArgs` / `MouseButtonEventArgs` ambiguity in hybrid apps**: With both `UseWindowsForms` and `UseWPF` enabled, `KeyEventArgs` and `MouseButtonEventArgs` types are ambiguous between the two namespaces. Either fully qualify (`System.Windows.Input.KeyEventArgs`) or add per-file `using` aliases. The `<Using Remove="System.Drawing" />` trick in the csproj only handles System.Drawing; it doesn't fix these.

## Achievement Icon Resolution

Steam/GBE achievement icons are 256x256 JPEG. Icon paths in `steam_settings/achievements.json` are relative to `steam_settings/` (e.g. `"icon": "img/abc123.jpg"`). Resolve with path traversal protection:

```csharp
var metaDirFull = Path.GetFullPath(metadataDir) + Path.DirectorySeparatorChar;
var exactPath = Path.GetFullPath(Path.Combine(metadataDir, iconName));
if (exactPath.StartsWith(metaDirFull, OrdinalIgnoreCase) && File.Exists(exactPath))
    return exactPath;
```
