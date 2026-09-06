# Watching another process's windows with SetWinEventHook

How to learn, immediately and cheaply, that a window in **another** process changed its title or came to the foreground. Measured September 2026 on Windows 11 26200 against Windows Terminal, from a Tauri/Rust GUI app.

## Scope the hook to a pid. This is the whole difference between usable and not.

```
SetWinEventHook(eventMin, eventMax, NULL, callback, idProcess, 0, WINEVENT_OUTOFCONTEXT)
```

Measured over the same desktop doing the same work:

| scope | events | window |
|---|---|---|
| global (`idProcess = 0`) | 986 | 34 s |
| one pid | 6 | 22 s |

792 of the 986 were `SysTreeView32` traffic from `explorer.exe`, and the rate was identical idle and busy, so the noise is not user driven and no amount of waiting makes it quieter. The OS does the pid filtering before the event ever reaches your process, so scoping is free. A global hook also has a documented side effect worth avoiding: `NotifyWinEvent` stops being a no-op session wide once anything is listening.

Resolve the pid from a window you can find (`EnumWindows` plus a class match, then `GetWindowThreadProcessId`) rather than from a process name, and re-resolve it periodically so a restart of the target is picked up.

## Constants and shapes that worked

- `EVENT_OBJECT_NAMECHANGE = 0x800C` for a title change, `EVENT_SYSTEM_FOREGROUND = 0x0003` for focus.
- `WINEVENT_OUTOFCONTEXT = 0x0000`, `hmodWinEventProc = NULL`. No DLL injection, no in-process hook.
- Register **two narrow ranges**, not one wide `min..max` spanning both, or everything between them arrives as noise you filter by hand instead of the OS filtering it.
- Filter on `idObject == OBJID_WINDOW (0)` and `idChild == CHILDID_SELF (0)`. Without it you also get the controls inside the window.
- `GetWindowTextW(hwnd)` called **inside** the callback already returns the new title. It reads the cached caption for another process's window rather than sending `WM_GETTEXT`, so it is cheap and cannot block on a hung target.
- Latency from the user action to the callback measured consistently under 100 ms.

## The registering thread needs a message pump

An out-of-context hook is delivered by posting to the message queue of the thread that registered it, so that thread must run `GetMessageW` / `TranslateMessage` / `DispatchMessageW` for the life of the hook. Two consequences:

- A dedicated non-UI thread is fine, and is what you want in a GUI app whose main thread belongs to the framework.
- On a silent desktop the loop blocks forever, so add `SetTimer(NULL, NULL, ms, NULL)` to wake it. Timers created with a NULL window post `WM_TIMER` to the thread queue, which is exactly what you need for periodic work like re-resolving the target pid.

## Rust: the callback cannot capture

`WINEVENTPROC` is a bare `unsafe extern "system" fn`, so there is nowhere to put state. The pattern that works:

```rust
static EVENTS: OnceLock<Sender<RawEvent>> = OnceLock::new();

unsafe extern "system" fn on_event(_hook: isize, event: u32, hwnd: isize, id_object: i32, id_child: i32, _thread: u32, _time: u32) {
    if id_object != 0 || id_child != 0 { return }
    let Some(tx) = EVENTS.get() else { return };
    let _ = tx.send(RawEvent { event, hwnd, title: window_text(hwnd), at_ms: now_ms() });
}
```

Push to a static channel and do every judgement on the receiving side. The callback must return fast or it drains USER resources for the whole desktop, so read only what is **true at that instant** (the foreground window, an idle clock, the clock) and let a consumer thread do the diffing. Values read later by the consumer are values from a different moment.

Declaring the imports by hand avoids a `windows`/`windows-sys` dependency:

```rust
type WinEventProc = unsafe extern "system" fn(isize, u32, isize, i32, i32, u32, u32);

#[link(name = "user32")]
extern "system" {
    fn SetWinEventHook(min: u32, max: u32, hmod: isize, cb: WinEventProc, pid: u32, thread: u32, flags: u32) -> isize;
    fn UnhookWinEvent(hook: isize) -> i32;
    fn GetMessageW(msg: *mut Msg, hwnd: isize, min: u32, max: u32) -> i32;
    fn SetTimer(hwnd: isize, id: usize, elapse: u32, cb: usize) -> usize;
}
```

`Msg` needs only the documented fields under `#[repr(C)]`; the x64 padding after `message` comes for free.

## An elevated target is silently invisible

UIPI stops a medium integrity process from receiving events about an elevated one. `SetWinEventHook` still **succeeds and returns a non-null handle**, and then nothing is ever delivered. A handle is therefore not evidence that the watch works, so log the first delivery rather than the installation, or a total failure reads exactly like a quiet desktop. `uiAccess` would lift it but needs a signed binary installed under `Program Files`.

## Diffing titles you wrote yourself

If the thing you are watching is a caption your own program publishes, a title change has two causes that look identical at the event: the user did something, or **you** rewrote it. Diff the identity the title encodes, never the string. A status glyph changing or a percentage ticking is your own write and must not read as a user action.

Relatedly, a change delivered by an event is known to within its own latency, while one discovered by polling is known only to within the interval. Where the distinction matters, credit the earlier bound: erring early is usually recoverable, erring late is usually not.

## Deciding whether a change was a person

`GetLastInputInfo` is desktop wide and says nothing about which window received the input. Composed with `GetForegroundWindow` it becomes useful: a change to a window that holds the foreground, arriving with the input clock near zero, was almost certainly a person, because clicking or keying **is** input. Measured against real usage, human driven changes arrived with idle under 50 ms while script driven ones (a CLI told to switch tabs) had either no recent input or no foreground. Both conditions together reject the scripted case and cost no real one.

See also `windows-terminal-title.md` for what Windows Terminal specifically exposes, and `windows-window-capture.md` for reading a window's pixels.
