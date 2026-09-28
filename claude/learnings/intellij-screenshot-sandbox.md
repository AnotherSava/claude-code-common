# Capturing an IntelliJ plugin's documentation screenshots from a scripted sandbox

A plugin's docs screenshots can be staged and captured by a script instead of by hand: a dedicated
sandbox IDE with JetBrains' Remote Robot server in it, driven over HTTP. Nearly every frame can then
be painted from inside the IDE, touching neither the screen nor the pointer; only what the OS draws
(popup shadows, a dialog's window frame) needs a screen read. Everything below was measured on
IntelliJ IDEA 2026.1 (IU-261) with robot-server 0.11.23 and the IntelliJ Platform Gradle Plugin 2.x
on Windows 11 at 150%.

## The sandbox task

Register a second run task rather than reusing `runIde`, so the docs sandbox pins its own IDE
release and flags:

```kotlin
val runIdeForScreenshots by intellijPlatformTesting.runIde.registering {
    type = IntelliJPlatformType.IntellijIdea
    version = "2026.1"
    task {
        jvmArgumentProviders += CommandLineArgumentProvider {
            listOf(
                "-Drobot-server.port=8582",
                "-Djb.privacy.policy.text=<!--999.999-->",
                "-Djb.consents.confirmation.enabled=false",
                "-Didea.initially.ask.config=never",
                "-Didea.trust.all.projects=true",
                "-Dide.show.tips.on.startup.default.value=false",
                "-Didea.suppress.statistics.report=true",
                "-Didea.plugins.host=http://127.0.0.1:9",
                "-Dsun.java2d.uiScale=1.5",
            )
        }
    }
    plugins { robotServerPlugin("0.11.23") }
}
```

- **`idea.plugins.host` pointed at a closed local port** is what keeps the Settings tree free of an
  update-count badge on *Plugins*. A fresh sandbox of a new release finds updates for its bundled
  plugins, and `PluginUpdatesService` computes that count again whenever the Settings dialog opens,
  so `UpdateSettings.setPluginsCheckNeeded(false)` does not remove it. With no marketplace reachable
  the count is empty (`ourAllUpdates` holds no downloaders), and nothing a shot shows depends on the
  network. The same property is read by `ApplicationInfoImpl` as the plugin repository URL.
- **`uiScale=1.5`** makes device pixels 1.5× logical ones, the same as a 150% display, so in-process
  paints and screen reads line up.
- **Launch `gradlew.bat` from a Python driver on Windows, not `bash gradlew`.** `CreateProcess`
  searches System32 before `PATH`, so a bare `bash` there is WSL's, which runs the whole build and a
  Linux IDE inside WSL (see `windows-spawning-bash.md`).

## Driving it

`POST http://127.0.0.1:8582/js/execute` with `{"script": "...", "runInEdt": true}` runs Rhino
JavaScript in the IDE; `GET /hello` answers once the server is up. Plugin classes are invisible to
Rhino by name: load them through the plugin's own class loader
(`PluginManagerCore.getPlugin(PluginId.getId("<id>")).getPluginClassLoader()`,
then `Class.forName(name, true, loader)`). Rhino keeps no state between calls, so prepend a prelude of
helpers to every script, and return data by having the script write JSON to a file the driver reads.

Stage through inputs the plugin already reads — its settings service, its `PropertiesComponent`
defaults, the fixture file it opens — so the editor is built in the wanted state rather than switched
into it. Reopening a file restores its per-file editor state over those defaults, so copy the fixture
under a fresh name for every shot.

## Painting a component in-process

Paint into a `TYPE_INT_RGB` image scaled by the ui scale, clipped to the component, then save with a
`pHYs` chunk for 144 dpi. Size the image with `Math.floor(w * scale)`: a logical size that scales to a
half pixel leaves its last row half painted, and an outline finder takes that row for subject.

- **The Islands theme draws the editor's rounded "island" in `EditorsSplitters`**, not in the editor,
  so a shot meant to show those corners paints that ancestor. Its arc is `Island.arc` 20 logical
  (a 15 px radius at 1.5), with a 1 px border over a tinted gradient backdrop.
- Hide editor tabs (`UISettings.setEditorTabPlacement(0)`) when the island's own corners should be
  the editor's, as they are in an IDE configured without tabs.

## A modal Settings dialog, opened by script

`DialogWrapper.show()` is modal, so calling it inside the robot's EDT script never returns. Schedule
it instead and poll for it:

```javascript
var U = com.intellij.ide.actions.ShowSettingsUtilImpl, p = project(), id = "<configurable id>";
ApplicationManager.getApplication().invokeLater(new java.lang.Runnable({run: function () {
    U.showSettingsDialog(p, id, null); }}), ModalityState.nonModal());
```

- **Open a page by configurable id, not by display name** — a `ColorSettingsPage` usually shares its
  plugin's display name. An `applicationConfigurable`'s id is the one in `plugin.xml`; a colour page's
  is `reference.settingsdialog.IDE.editor.colors.` followed by the `ColorSettingsPage` class name.
- Find the open dialog with `DialogWrapper.findInstance(window) instanceof SettingsDialog` over
  `Window.getWindows()`. `dialog.getEditor()` is a `SettingsEditor`: `getSelectedConfigurableId()`,
  `getTreeView().getTree()`, and the private fields `loadingDecorator` (wait while `isLoading()`) and
  `mySplitter` (the tree/page split; set its proportion to fix the tree width).
- **Settle before capturing**: wait until the page id matches, loading is done, and the layout of the
  window is identical on two polls in a row; then `paintImmediately` the root pane.
- The page's own scroll pane holds a `DialogPanel`; the dialog is tall enough when its preferred height
  fits the viewport. The Color Scheme page enforces a minimum dialog height (707 logical at 1.5).
- Clear persisted state first — `settings.editor.splitter.proportion` and `selected.color.option.type`
  in `PropertiesComponent` — since the sandbox's config outlives every launch. A selected colour key
  blinks its ranges in the preview, so a screen read can catch either phase: keep none selected.
- **An open modal dialog holds back `Application.exit()`**, so a stop routine must cancel it
  (`doCancelAction()`) before asking the IDE to exit, or the wait for exit times out.

## Capturing the dialog as a whole window

The dialog's rounded corners and border are drawn by DWM at composition, so only a screen read has
them (`windows-window-capture.md`, `windows-11-dwm-frame.md`). Hand the shutter the dialog's own
handle, `com.sun.jna.Native.getWindowID(window)`, since the title "Settings" also matches the Windows
Settings app. Java's window bounds include the invisible resize margins (7 logical px left, right and
bottom here), which DWM's extended frame bounds leave out, so the captured PNG is smaller than the
bounds × scale. Put the sandbox's own frame behind the dialog first: the capture's corner wedges and
translucent border show whatever lies behind the window, and that should be the IDE rather than the
user's other windows.
