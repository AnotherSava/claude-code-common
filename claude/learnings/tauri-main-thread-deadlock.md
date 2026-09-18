# Deadlocking a Tauri v2 app with one ordinary mutex

A lock held across a Tauri call that hops to the main thread freezes the whole application, because the main thread is itself a caller that can want the same lock. The two halves are written in different files by different people, neither looks wrong, and the result is not a slow app — it is a dead event loop, recoverable only by killing the process. Tray Quit needs the main thread too.

This cost a shipped regression in claude-code-dashboard on 2026-09-18: a `Mutex<()>` added to order two concurrent emits, reviewed and reverted the same day.

## Which calls hop to the main thread and wait

Tauri wraps these in `run_item_main_thread!` or `window_getter!`, both of which post a task to the event loop and then block on `rx.recv()`:

- Menu item mutation — `CheckMenuItem::set_checked`, `MenuItem::set_text`, and the rest of the menu API
- Tray mutation — `TrayIcon::set_icon`, `set_tooltip`, `set_title`
- Window geometry reads — `Window::scale_factor`, `inner_size`, `outer_position`

The blocking is conditional in a way that hides it: `send_user_message` runs the task inline when the caller *is* the main thread, so every one of these is instant in a `setup()` hook or a menu handler and blocks only from a background thread. A call tested interactively from the tray therefore never shows the behaviour that deadlocks.

`Emitter::emit` is not in this set. It posts an `EvaluateScript` message with no reply channel, so it returns without waiting.

## Why the main thread wants your lock too

A `#[tauri::command]` that is not `async` runs **inline on the main thread**, inside the webview's IPC callback. So every sync command is a path from the main thread into whatever that command touches — and a command that calls a shared helper reaches every lock the helper takes, several call levels down from anything that looks like UI code.

Tray menu events arrive the same way: Tauri routes them through the event-loop proxy, so a menu handler runs on the main thread as well.

## The shape

A background thread — an HTTP handler, a file watcher, a timer — takes the lock and then calls one of the hopping APIs. It parks waiting for the main thread. Before the event loop dequeues that task, the user clicks something, the main thread runs a sync command inline, and the command blocks on the lock the background thread holds. Neither ever returns.

The window is the interval between posting the task and the loop processing it, which is short. The thing that makes it fire in practice is frequency: an emit path that runs on every state change opens that window thousands of times a day.

## Finding it

Grep for the hop rather than for the lock, since the lock is the innocent-looking half:

```sh
rg 'set_checked|set_text|set_icon|set_tooltip|scale_factor|inner_size|outer_position|run_on_main_thread' src/
```

Then ask, for each hit, whether any lock is held at that point, and whether any sync command can reach that same lock. A helper called from both a background service and a command is the shape to look for.

## Ordering without serializing

Serializing is usually the wrong instrument anyway. Where the goal is that a stale writer must not overwrite a fresh one, order the writes instead of the writers:

Mint a monotonic ticket inside the lock that already guards the data being read, so ticket order is content order:

```rust
pub fn snapshot_versioned(&self) -> (u64, Vec<Row>) {
    let rows = self.rows.lock().unwrap();
    let seq = self.seq.fetch_add(1, Ordering::Relaxed) + 1;
    (seq, rows.clone())
}
```

Carry the ticket to the consumer that publishes somewhere durable, and have it stand down under the lock it already takes:

```rust
let mut applied = self.applied.lock().unwrap();
if seq <= *applied { return; }
*applied = seq;
```

Mint the ticket **before** the clone, not after. A ticket taken after the copy finishes orders the writers by how long their copy took, which a slow clone reverses.

Two properties this keeps that a global lock loses: no caller waits on another, so no main-thread hop can ever be under a contended lock; and the check is free where nothing raced, because the consumer already holds that lock to do its work.

Consumers whose output the next update overwrites anyway need no ticket. Reserve it for output that outlives the process — a window title, a file, a tray caption — where a stale value sits until something else happens to move it.

## Log the stand-down

Emit a line when a consumer refuses a stale ticket. Standing down and never racing are otherwise the same silence, so without it there is no way to tell a working ordering from a race that stopped happening on its own.
