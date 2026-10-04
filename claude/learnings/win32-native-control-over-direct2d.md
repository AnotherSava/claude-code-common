# Overlaying a native child control on a Direct2D window

A Win32 app that paints its whole client area with Direct2D and drops a native control (an `EDIT`
for inline rename, a combo box, a spin control) on top of that surface has two ways to get it
wrong, and both present as cosmetic bugs rather than as errors. Measured on agwinterm, a
Direct2D terminal whose sidebar rows are renamed through a child `EDIT`.

## The parent paints over the child without WS_CLIPCHILDREN

A window created without `WS_CLIPCHILDREN` is not clipped around its children, so everything the
parent draws inside a child's rectangle lands on screen until the child's next `WM_PAINT` restores
it. The child then repaints, the parent's next frame overwrites it again, and the result is a
flicker confined to whatever the parent happens to draw under the control.

Two details make it hard to read from the symptom:

- **It is intermittent, and the rate follows unrelated load.** `InvalidateRect(hwnd, NULL, …)`
  dirties the children too — that is `RedrawWindow`'s documented default — and `WM_PAINT` is the
  lowest-priority message, delivered only when the queue holds nothing else. So the parent's frame
  sits on screen until the queue drains enough for the child's restoring paint: invisible when the
  app is idle, tens of milliseconds when it is busy. A user reports it as happening "at random".
- **Guarding individual draw calls does not fix it.** The obvious reading is to skip the glyphs
  that overlap the control. It fails, because the parent also issues a full-surface
  `rt.Clear(...)` and usually a background `FillRectangle` over the whole region, and neither has
  any per-item condition to hang a guard on. Guarding the glyphs stops *those* flickering and
  starts the control's own background and text flickering instead — a strictly worse bug, since it
  is now the text the user is typing.

Setting the flag at creation is the whole fix:

```csharp
CreateWindowExW(0, ClassName, AppName, WS_OVERLAPPEDWINDOW | WS_CLIPCHILDREN, …)
```

`WS_CLIPCHILDREN` is `0x02000000`. That matters when some other code path strips a style mask:
`WS_OVERLAPPEDWINDOW` is `0x00CF0000`, so a fullscreen toggle doing
`style & ~WS_OVERLAPPEDWINDOW` leaves the clip bit in place. Check the arithmetic for whatever
mask the app strips rather than assuming.

**The documentation does not settle whether a Direct2D present honours it**, because the clip MSDN
describes is the one `BeginPaint` installs on the paint HDC, and a D2D app never draws through
that HDC. It does honour it: tested on a `ID2D1HwndRenderTarget` created with
`PresentOptions.None` that clears and redraws the full client every frame, the flicker stopped
outright. Nothing about retained contents is involved, so the flag is safe for the
clear-every-frame style.

Worth checking alongside it: nothing in Win32 repositions or hides a child control when the layout
under it moves. Once the parent is clipped, a control left up over a newly-opened overlay stays
visible on top of it, where before it was merely painted over. If a click can open such an overlay
without moving focus — `EN_KILLFOCUS` fires only when focus actually leaves — commit or destroy
the control on that path explicitly.

## GDI takes device pixels, DirectWrite takes DIPs

A control overlaid on D2D-drawn text has to match that text's size, and the two APIs do not
measure in the same unit:

- `IDWriteTextFormat`'s font size is an **em size in DIPs**.
- `CreateFontW(nHeight, …)` takes **logical units**, and a *negative* value means the character
  (em) height rather than the cell height.

So the conversion is `CreateFontW(-ToDevice(format.FontSize), …)`, where `ToDevice` applies the
window's DPI scale. A hardcoded pixel size silently matches only one DPI and only one configured
font size.

**Read the size off the format whose text the control covers, rather than repeating a literal.**
`IDWriteTextFormat.FontSize` is readable, so each call site can pass the size of the exact format
it is overlaying:

```csharp
EnsureEditGdi(_sidebarFont.FontSize);   // the box sits over sidebar row text
EnsureEditGdi(_uiFont.FontSize);        // this one sits over the title text
```

That removes the drift rather than fixing an instance of it. The bug it replaced was a single
`ToDevice(13)` shared by both call sites, correct for the fixed-size title bar and wrong for a
sidebar font the user can configure from 9 to 20 — the rename box drew at 13 over 20-point rows.
Two call sites needing different sizes is also why a shared constant is the wrong fix here.

Cache the resulting `HFONT` by pixel height, not per window: windows on monitors at different
scales converge on the same handle whenever their computed pixel size matches.
