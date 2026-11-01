# WinForms FolderBrowserDialog: SelectedPath vs InitialDirectory

On modern .NET (measured on .NET 10), `FolderBrowserDialog` (the Vista-style picker) has two properties that sound
interchangeable and are not:

| Property | What the picker shows |
|---|---|
| `SelectedPath = @"C:\Games"` | Opens the **parent** (`C:\`) with `Games` highlighted and its name in the Folder box. Pressing Select returns `C:\Games` itself. |
| `InitialDirectory = @"C:\Games"` | Opens **inside** `C:\Games`, nothing highlighted, ready for the user to pick a folder below it. |

So the choice depends on what the folder means to the user:

- When it is the **current value** being re-confirmed or changed (an edit box already holding a
  path), use `SelectedPath`. Highlighting it in its parent is right.
- When it is a **place to start browsing** for something underneath (a games library root, where the
  user is about to pick one game's folder), use `InitialDirectory`. `SelectedPath` there opens one
  level too high, and an accidental Select returns the root itself.

Observed 2026-11-01 on Windows 11: a wizard passed a games root through `SelectedPath`, meaning
"start here", and the picker opened at the drive root with the games folder highlighted. Moving the
value to `InitialDirectory` fixed it. What the picker does with both set was not measured, so a
helper that accepts both should set only the one the call site actually means.
