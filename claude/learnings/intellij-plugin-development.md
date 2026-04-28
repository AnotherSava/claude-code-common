# IntelliJ Platform plugin development

Reference for IntelliJ Platform plugins built with the **IntelliJ Platform
Gradle Plugin 2.x**. Focuses on items that aren't obvious from a casual read
of official docs — real gotchas, API patterns, and platform limits surfaced
while building a production plugin.

## Project setup

- **Tooling baseline**: Gradle 8.5+, JDK 17. The IntelliJ Platform Gradle
  Plugin 2.x refuses older Gradle; target IntelliJ's bundled JBR 17+ for
  build.
- `plugins { id("org.jetbrains.intellij.platform") version "2.x" }` — the
  `.platform` flavor is the current one; the old `org.jetbrains.intellij`
  (1.x) is deprecated.
- **Broad IDE compat**: depend only on `<depends>com.intellij.modules.platform</depends>`
  in `plugin.xml`. Plugin then loads in every IntelliJ-based IDE (IDEA,
  PyCharm, WebStorm, Rider, GoLand, CLion, DataGrip, RubyMine, RustRover,
  PhpStorm). Resolve JSON / other language features at runtime via
  `FileTypeManager.getFileTypeByExtension(...)` with a `PLAIN_TEXT` fallback.
- `sinceBuild = "241"` (IDEA 2024.1) + open `untilBuild` is a reasonable
  bottom line — 241 shipped current `Alarm`, `SearchTextField`, Kotlin UI
  DSL v2, `ComboBoxAction.createPopupActionGroup(JComponent)`.
- For local iteration, `gradle runIde` launches a sandbox IDE with the
  plugin preloaded; for on-your-real-IDE deploy, extract the built zip into
  `%APPDATA%/JetBrains/<IDE><version>/plugins/`.

## Extension points in a split-editor plugin

```xml
<extensions defaultExtensionNs="com.intellij">
    <fileType name="PLAIN_TEXT" extensions="jsonl"/>
    <fileEditorProvider implementation="…"/>
    <applicationService serviceImplementation="…"/>
    <applicationConfigurable parentId="tools" instance="…" displayName="…"/>
    <colorSettingsPage implementation="…"/>
</extensions>

<actions>
    <action id="…" class="…" text="…">
        <add-to-group group-id="EditorPopupMenu" anchor="first"/>
    </action>
    <group id="MyPlugin.ViewerPopup">
        <reference ref="MyPlugin.SomeAction"/>
        <separator/>
        <reference ref="$Copy"/>
    </group>
</actions>
```

`$Copy` is the canonical ID for the standard Copy action. You reference it
with `<reference ref="$Copy"/>`, not as a separate action registration.

## Editor pane gotchas

### Right-margin vertical guide

Editors draw a vertical line at the hard-wrap column by default (120 chars).
For log viewers or any editor where code-wrap hints are noise:

```kotlin
editor.settings.isRightMarginShown = false
```

Applies to both real `TextEditor` and synthetic editors from
`EditorFactory.createViewer(...)`.

### Viewer editors get a minimal context menu by default

`EditorFactory.createViewer(doc, project, EditorKind.PREVIEW)` produces an
Editor whose default context menu is empty/Copy-only — `EditorPopupMenu`
isn't wired in automatically. To get your custom actions:

```kotlin
(editor as? EditorEx)?.setContextMenuGroupId("MyPlugin.ViewerPopup")
```

Usually you want a **minimal** group (your custom action + `$Copy`), not
the full `EditorPopupMenu` — read-only viewers don't benefit from refactor /
goto / inspect entries, and users find them confusing.

### Real `TextEditor` vs synthetic viewer trade-off

- Real `TextEditor` (from `TextEditorProvider.createEditor(project, file)`)
  is bound to the `VirtualFile`: save/reload/external-change detection work.
- Synthetic viewer (from `EditorFactory.createViewer`) is over a standalone
  `Document`: no file binding, read-only, but state (caret, scroll,
  selection) can survive across document replacements since you control the
  document's lifetime.

For log-viewer-style plugins where the user rarely edits, preferring the
synthetic viewer as the always-shown raw pane simplifies state management.
Keep the real `TextEditor` alive behind the scenes for document event
listening + IDE file-system integration, but never add it to the visible UI.

### Sizing a container to fit an editor's content exactly

Don't trust two seemingly-obvious measurements when auto-sizing a panel
to its editor's content:

- `EditorEx.contentSize.height` — varies based on whether a horizontal
  scrollbar is currently visible. Same document produces different
  readings depending on the surrounding scroll-pane state.
- `JScrollPane.horizontalScrollBar.preferredSize.height` — returns 0
  when the scrollbar is currently hidden (JBScrollBar overlay mode), or
  its real height when visible.

Adding both to a target height double-counts the scrollbar after one
navigation and undercounts after another, producing an auto-sized panel
that oscillates as the user moves between content with/without
horizontal overflow.

Reliable: derive the target purely from the document plus constants:

```kotlin
val docH = doc.lineCount * editor.lineHeight
val targetH = docH + borderH + JBUI.scale(11)  // constant scrollbar reservation
```

Also disable the editor's virtual scroll padding so `lineCount *
lineHeight` matches what the editor actually paints (without an extra
blank page below the content):

```kotlin
(editor as EditorEx).settings.let {
    it.additionalLinesCount = 0
    it.isAdditionalPageAtBottom = false
}
```

### `JLayeredPane` + custom `LayoutManager` doesn't render overlays reliably

`JLayeredPane` treats `add(comp, IntegerLayer)` specially — the Object
constraint becomes the layer, not a layout hint. Combined with a custom
`LayoutManager`, child bounds are set but the overlay frame may not
paint on top of the default layer.

Workaround: plain `JPanel(null)` with explicit z-order:

```kotlin
val container = JPanel(null)
container.layout = MyLayout(...)
container.add(background)
container.add(overlay)
container.setComponentZOrder(overlay, 0)  // 0 = front
```

### Transparent overlays need their own `JComponent` for mouse events

Swing dispatches mouse events to the deepest visible component — no
bubbling. A transparent area on top of a `JScrollPane` (e.g. a resize
grip overlapping the editor's bottom-left) will not deliver clicks to a
listener installed on the outer panel; the scrollpane consumes them.

Make the interactive overlay its own `JComponent` at z-order 0, with
its own mouse listeners. Don't try to listen on the parent.

### Click-through decoration components

The opposite problem: a paint-only decoration that should *not* intercept
mouse events. Default Swing dispatch routes clicks on a `JComponent`'s
bounds to its listeners (or consumes the event with no handler), blocking
underlying components like a `JScrollBar` from receiving drags.

Override `contains(x, y)` to return false:

```kotlin
private inner class Decoration : JComponent() {
    init { isOpaque = false }
    override fun paintComponent(g: Graphics) { /* draw stuff */ }
    override fun contains(x: Int, y: Int): Boolean = false
}
```

Swing skips the component during hit-testing, so events fall through to
the next visible component beneath. Paint and hit-test are independent —
the component still draws normally.

Use case: a 1px divider drawn across a scrollbar gutter so an overlay's
visual frame extends past its own bounds. The line is visible everywhere
it covers, and the scrollbar beneath it stays draggable.

### Soft-wrap

Wrap width is editor-wide. `EditorSettings.setUseSoftWraps(true)` enables
soft wrap for the whole editor; the wrap point is derived from the
visible viewport width. There is no public API for per-line variable
wrap widths. Per-line wrap requires either subclassing
`SoftWrapApplianceManager` via reflection on
`SoftWrapModelImpl.myApplianceManager` (internal, brittle across IDE
versions) or rewriting the document with hard newlines and maintaining a
`displayed → logical` line map for caret / filter translation. Avoid
both unless the use case is critical.

Custom soft-wrap indent has an off-by-one. `setUseCustomSoftWrapIndent(true)`
+ `setCustomSoftWrapIndent(N)` indents wrapped continuations by N columns
*plus* the width of the soft-wrap indicator glyph IntelliJ paints at the
head of every continuation line. For monospace fonts the glyph occupies
~1 column, so visible text starts at column `N + 1`. To align text at
column `X`, set `customSoftWrapIndent = X - 1`.

Because the indent is editor-wide, it only produces precise alignment
when every line's wrap point shares the same column (e.g. all lines are
padded to the same prefix length). Under variable prefix lengths, prefer
`setUseCustomSoftWrapIndent(false)` over a single best-effort
approximation — every wrong-by-a-few-columns wrap looks like a bug.

## Highlighting strategies

### Theme-integrated colors via `TextAttributesKey` + `ColorSettingsPage`

The "correct" way to expose colors users can customize:

```kotlin
object MyColors {
    val TIMESTAMP = TextAttributesKey.createTextAttributesKey(
        "MYPLUGIN_TIMESTAMP", DefaultLanguageHighlighterColors.LINE_COMMENT
    )
    // … one key per semantic element
}

class MyColorSettingsPage : ColorSettingsPage {
    override fun getDisplayName() = "My Plugin"
    override fun getHighlighter(): SyntaxHighlighter = PlainSyntaxHighlighter()
    override fun getAttributeDescriptors() = arrayOf(
        AttributesDescriptor("Timestamp", MyColors.TIMESTAMP),
        // …
    )
    override fun getDemoText(): String = "<ts>2026-04-22</ts> <lvl>INFO</lvl> hello"
    override fun getAdditionalHighlightingTagToDescriptorMap() = mapOf(
        "ts" to MyColors.TIMESTAMP,
        "lvl" to MyColors.LEVEL,
    )
    override fun getColorDescriptors(): Array<ColorDescriptor> = ColorDescriptor.EMPTY_ARRAY
}
```

Register `<colorSettingsPage implementation="…"/>`. The page appears under
**Settings → Editor → Color Scheme → <display name>**. Users customize
colors the same way they customize Java/Kotlin syntax colors — inheritance,
scheme export, and IDE theme switching all Just Work.

`DefaultLanguageHighlighterColors.*` gives language-neutral fallbacks
(`LINE_COMMENT`, `METADATA`, `KEYWORD`, `IDENTIFIER`, `STRING`,
`INSTANCE_FIELD`, `OPERATION_SIGN`, `NUMBER`, `BLOCK_COMMENT`) that look
reasonable in every theme before a user customizes them.

### ConsoleViewContentType.LOG_*_OUTPUT is theme-unstable

In some schemes `LOG_INFO_OUTPUT` maps to yellow, `LOG_WARNING_OUTPUT` maps
to default text, etc. If you want consistent log-level colors regardless of
the user's scheme, **don't** do:

```kotlin
// fragile — appearance varies by IDE theme
ConsoleViewContentType.LOG_INFO_OUTPUT.attributes
```

Register your own `TextAttributesKey` per severity with an appropriate
`DefaultLanguageHighlighterColors.*` fallback.

### Custom `EditorHighlighter` via sidecar hints

For a formatter that generates structured text where token boundaries are
known to the producer but would need heuristic lexing to recover:

```kotlin
val MY_SPANS: Key<List<Span>> = Key.create("my.plugin.spans")

data class Span(val start: Int, val end: Int, val key: TextAttributesKey?)

class MyHighlighter(private val doc: Document) : EditorHighlighter {
    @Volatile private var scheme: EditorColorsScheme =
        EditorColorsManager.getInstance().globalScheme

    override fun createIterator(startOffset: Int): HighlighterIterator {
        val spans = doc.getUserData(MY_SPANS) ?: emptyList()
        return Iter(spans, doc, scheme, startOffset)
    }
    override fun setColorScheme(s: EditorColorsScheme) { scheme = s }
    override fun setEditor(e: HighlighterClient) {}
    override fun beforeDocumentChange(e: DocumentEvent) {}
    override fun documentChanged(e: DocumentEvent) {}
}

// Attach once:
(editor as? EditorEx)?.highlighter = MyHighlighter(doc)

// Publish new spans atomically with document text:
runWriteAction {
    doc.setText(newText)
    doc.putUserData(MY_SPANS, freshSpans)
}
```

The `HighlighterIterator` is a cursor with 8 methods: `getStart`, `getEnd`,
`getTokenType` (return `TokenType.WHITE_SPACE` if you don't need semantic
tokens), `getTextAttributes`, `advance`, `retreat`, `atEnd`, `getDocument`.

**Continuous coverage**: the iterator should return a span for every
offset in the document. Pre-compute gap-filler spans with `key = null` so
paint is seamless.

**Why sidecar instead of a proper `SyntaxHighlighter` + `Lexer`**:
- No FileType / Language / ParserDefinition scaffolding needed.
- Boundaries are exactly what the formatter emitted — no heuristic
  re-lexing that might mis-tokenize ambiguous cases.
- Document user data is mutable and thread-safe; setText + putUserData in
  a single `runWriteAction` keeps spans synchronized with text.

Avoids 50k+ `RangeHighlighter` objects in the MarkupModel for large files
and delegates paint to IntelliJ's native pipeline.

## State persistence

### `PersistentStateComponent` — property-name gotcha

```kotlin
@State(name = "MyPluginSettings", storages = [Storage("MyPluginSettings.xml")])
@Service(Service.Level.APP)
class MySettings : PersistentStateComponent<MySettings.State> {
    data class State(
        var schemaVersion: Int = 1,   // reserve for future migrations
        var fooEnabled: Boolean = true,
        // …
    )

    private var backing: State = State()
    val config: State get() = backing

    override fun getState(): State = backing
    override fun loadState(s: State) { backing = migrate(s) }

    private fun migrate(s: State): State { /* ... */ return s }
}
```

Naming the property `state` (`var state: State`) clashes with the
auto-generated `getState()` Kotlin produces for it — compile fails with
"Platform declaration clash". Use `backing` or `currentState`; expose via
a `config` val if external code needs to read it.

Always reserve a `schemaVersion: Int = 1` field from day one — cheap,
future-proofs migrations. Without it, a later rename or enum change that
can't be handled by "silently drop unknown fields" has no clean place to
hook into.

### `FileEditorState` for per-file state

When state should persist per `.someExt` file (pane selection, filters,
scroll position), not globally:

```kotlin
class MyFileEditorState(
    var pane: Pane = Pane.DEFAULT,
    var filterText: String = "",
) : FileEditorState {
    // JDOM-based reflection needs a no-arg constructor:
    constructor() : this(Pane.DEFAULT, "")
    override fun canBeMergedWith(other: FileEditorState, level: FileEditorStateLevel) = false
}
```

Provider serializes attributes on a JDOM `Element`:

```kotlin
override fun writeState(state: FileEditorState, project: Project, target: Element) {
    if (state !is MyFileEditorState) return
    target.setAttribute("pane", state.pane.name)
    if (state.filterText.isNotEmpty()) target.setAttribute("filterText", state.filterText)
}

override fun readState(source: Element, project: Project, file: VirtualFile): FileEditorState {
    val state = MyFileEditorState()
    source.getAttributeValue("pane")?.let { raw ->
        Pane.values().firstOrNull { it.name == raw }?.let { state.pane = it }
    }
    state.filterText = source.getAttributeValue("filterText").orEmpty()
    return state
}
```

FileEditor implements `getState(level)` + `setState(state)`. IntelliJ calls
`setState` right after `createEditor`, so state restoration fires on open.

Persisted per-file state is stored in the project's workspace XML, so it
rides along with project export/sync.

## Live-update pattern with `MessageBus`

```kotlin
interface MyListener {
    fun changed()
    companion object {
        val TOPIC: Topic<MyListener> = Topic("my.plugin.changes", MyListener::class.java)
    }
}

// Publisher (e.g. after settings.apply):
ApplicationManager.getApplication().messageBus
    .syncPublisher(MyListener.TOPIC)
    .changed()

// Subscriber (in FileEditor.init):
ApplicationManager.getApplication().messageBus.connect(this)  // 'this' = the FileEditor as Disposable
    .subscribe(MyListener.TOPIC, object : MyListener {
        override fun changed() { /* rebuild view */ }
    })
```

Passing the `FileEditor` (which extends `Disposable`) as the connect
argument makes the subscription unregister automatically on editor close —
no leak-prone manual cleanup.

## Platform limitations worth knowing

### Zero-height line hiding is not supported

`FoldRegion` always reserves one rendered line with a placeholder (`…` or
custom text). Setting placeholder to `""` still leaves the collapse marker
visible as one line. There's no `FoldRegion.setCollapsedHeight(0)`.

Workarounds that **don't** work:
- Inlays (`EditorCustomElementRenderer`) add zero-height content, they
  don't hide existing text.
- Wrapping `Document` with a filtered-view class — `DocumentImpl`-specific
  instanceof checks elsewhere in the platform prevent this.
- Abusing `EditorImpl` internals — `@ApiStatus.Internal`, breaks across
  versions.

If you need "filter out some lines entirely", the two viable options are:
1. Fold with placeholder (visible artifacts in exchange for preserved state).
2. Two editors — swap between the real `TextEditor` and a synthetic viewer
   over filtered content (clean visuals, state reset on swap).

### `Document` is tightly coupled to `DocumentImpl`

Any scheme that tries to present a subset/view over a `Document` without
inheriting from `DocumentImpl` will hit instanceof checks in the platform
and lose functionality (selection, inspections, etc.).

### Editor internal APIs

`EditorImpl`, `HighlighterClient`, some `EditorEx` methods are
`@ApiStatus.Internal`-adjacent. They're stable in practice but JetBrains
reserves the right to evolve them. For long-lived plugins, prefer:
- `Editor` / `EditorEx` (public) over `EditorImpl` (internal).
- `EditorHighlighter` interface (public) over subclassing
  `LexerEditorHighlighter` if the Lexer path isn't your natural fit.

## Kotlin incremental-compile ABI drift

When changing a heavily-used data class (especially a
`PersistentStateComponent`'s State class) in a way that alters the
synthetic-constructor signature, Kotlin's incremental compile can keep
test bytecode linked against the **old** synthetic signature:

```
java.lang.NoSuchMethodError: 'void com.myapp.State.<init>(…, kotlin.jvm.internal.DefaultConstructorMarker)'
```

at runtime, even though `gradle compileKotlin` reports success.

Fix: `gradle --rerun-tasks test` or `gradle clean test`. Don't spend time
hunting for the "missing field" — it's a cache issue.

This shows up especially when a named-argument constructor call in test
code references `MyDataClass$default(...)` with the old parameter count.

## Toolbar patterns

IntelliJ's `DefaultActionGroup` + `ActionManager.createActionToolbar(place, group, horizontal=true)`
is the standard shell. Inside, action types that matter:

| Action type | Use for |
|---|---|
| `AnAction` | Buttons (click → perform something) |
| `ToggleAction` | Checkable buttons (`isSelected` / `setSelected`) |
| `ComboBoxAction` | Dropdown with popup group of sub-actions |
| `Separator.create(text)` | Visual separator with optional inline label |
| `CustomComponentAction` | Render an arbitrary `JComponent` (JLabel, JTextField, JComboBox) inline |

For dropdowns driven by dynamic lists (targets in a file, recent searches,
etc.): subclass `ComboBoxAction` and override `createPopupActionGroup` to
rebuild the menu from current state on each open. Override `update(e)` to
set the button label to the current selection.

For direct Swing components (`SearchTextField`, bespoke `JComboBox`):
implement `CustomComponentAction.createCustomComponent(presentation, place)`
and return the component. Stash a reference to it in the action if external
code needs to update its state later.

`getActionUpdateThread()`: recent IntelliJ (241+) requires every `AnAction`
to declare whether `update()` runs on EDT or BGT. If your `update` reads
mutable UI-adjacent state (a settings service, a session object), return
`ActionUpdateThread.EDT` explicitly; otherwise the platform warns.
