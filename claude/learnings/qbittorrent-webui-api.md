# Driving qBittorrent from a script: the Web API, the run-on-finish hook and resume data

Source references are to qBittorrent's tag `release-5.1.0`, read on 2026-09-24. **Trust the source over the wiki:** the "WebUI API (qBittorrent 5.0)" wiki page omits `downloadPath`, `useDownloadPath`, `contentLayout`, `stopped`, `stopCondition` and the export endpoint, all of which exist.

## Turning the Web UI on for local scripts only

- Set `WebUI\Address` to `127.0.0.1` first. Its default is `*`, which also listens on every other interface, a VPN adapter included.
- `WebUI\LocalHostAuth=false` ("Bypass authentication for clients on localhost") makes loopback requests need no login; qBittorrent starts a session for them itself (`WebApplication::isAuthNeeded`, `src/webui/webapplication.cpp`). Any program on the machine can then drive qBittorrent.
- Without the bypass, a request answers HTTP 403, which is neither the add's `Fails.` nor a connection error. Report it as its own case.
- The keys live in `src/base/preferences.cpp`; the session keys in `src/base/bittorrent/sessionimpl.cpp`.

## Adding a torrent: `POST /api/v2/torrents/add`

Parameters, from `TorrentsController::addAction` in `src/webui/api/torrentscontroller.cpp`: `urls` (a magnet works), `savepath`, `downloadPath`, `useDownloadPath`, `contentLayout` (`Original`, `Subfolder`, `NoSubfolder`), `category`, `tags`, `rename`, `stopped`, `stopCondition` (`None`, `MetadataReceived`, `FilesChecked`).

- **The answer is `Ok.` or `Fails.`**, both with HTTP 200. `Fails.` covers a torrent that is already present (even when qBittorrent merges its trackers into the existing one), a magnet still being added, and an invalid magnet alike, so it can't say "already added" alone. `GET /api/v2/torrents/info?hashes=<hash>` can.
- **Sending `savepath` forces manual mode** (no automatic torrent management), so the paths are used as given.
- **Send `stopped=false` and `stopCondition=None` explicitly**, or the global "don't start automatically" option or a "metadata received" stop condition leaves the torrent stopped, and a success reported by the script is wrong.
- **`NoSubfolder` strips each release's root folder.** With one shared `downloadPath`, two torrents holding a file of the same relative name (`01.avi`, `Sample.mkv`, `Subs/Rus.srt`) write to the same path. Give each torrent its own staging folder, for example `<staging root>/<info-hash>`.
- **Re-adding into a folder that already holds some of the torrent's files moves them out.** `FileSearcher::search` looks for the files at the save path first. When it finds any there and the torrent is incomplete, `adjustStorageLocation` moves *all* of them to the download path until the torrent finishes, and moves them back afterwards. For an updated release added into a media library, the episodes already there leave the library for the length of the download. Add such a torrent with `useDownloadPath=false`.
- On the same volume, the move from download path to save path is a per-file rename (libtorrent's `move_storage` in `src/storage_utils.cpp`), so it is instant. A rename that fails rolls back and counts as a failed move.

## The "Run external program on torrent finished" hook

From `Application::runExternalProgram` in `src/app/application.cpp`:

- **It runs after the move** from the download path to the save path has finished, and also after a *failed* move (`TorrentImpl::handleMoveStorageJobFinished` runs the queued finished trigger either way).
- **Placeholders:** `%N` name, `%L` category, `%G` tags, `%F` content path, `%R` root path, `%D` save path, `%C` file count, `%Z` total size, `%T` current tracker, `%I` v1 info-hash, `%J` v2 info-hash, `%K` torrent ID.
- **`%D` is always the configured save path**, wherever the files actually are; `%F` is where they are. A hook can detect a failed move by `%F` not lying under `%D`.
- **Use `%K`, not `%I`, to address the torrent in the API.** A hybrid (v1+v2) torrent's ID becomes its truncated v2 hash once metadata arrives, and `getTorrent` looks up by ID only, so a lookup by `%I` answers 404.
- **The program starts with no working directory set and its standard handles closed**, under `CREATE_NO_WINDOW` while "Show console window" (`AutoRun\ConsoleEnabled`) stays off. So use absolute paths for the program and its script, and have the script resolve its own files from its own location; an error it prints goes nowhere, so it should log to a file.

## Shutting it down, which the API is the only clean route to

There is no CLI shutdown. `cmdoptions.cpp` defines `--save-path`, `--add-stopped`, `--skip-dialog`, `--category`, `--sequential`, `--first-and-last` and `--seed-mode` for adding a torrent, and nothing that stops the application. The endpoint is `POST /api/v2/app/shutdown`, so stopping it from a script means the Web UI is already on.

- **A tray-resident instance has no window to close.** `Get-Process qbittorrent` reports `MainWindowHandle == 0` once it is minimised to the tray, so `CloseMainWindow()` returns having sent nothing and the process sits there responding. Nothing distinguishes that from a close the application ignored, and waiting longer never helps.
- **Turning the Web UI on costs one manual exit.** qBittorrent rewrites `qBittorrent.ini` from memory when it exits, so keys written while it runs are discarded. The order is: have the user exit from the tray once, write `WebUI\Enabled`, `WebUI\Address` and `WebUI\LocalHostAuth`, restart — and every later cycle is `app/shutdown`. Read this section *before* concluding the application cannot be stopped: asking a second time for a tray exit is what happens otherwise.
- **Never run `qbittorrent.exe --help` on Windows.** It is a GUI subsystem binary, so the usage text goes to a modal dialog on the user's desktop and stdout stays empty. The command appears to hang, and the dialog sits in front of whatever they were doing.

## Editing `.fastresume` offline, to relocate or rename a torrent

Renaming the files a torrent seeds, or moving them, breaks it: libtorrent looks for the old names and the torrent errors with `fast resume rejected … mismatching file size`, which it also reports for a file that is simply gone. Repairing it means rewriting the resume data, and with the Web UI off that is the only route. Everything below is bencoded, in `BT_backup` beside the `.torrent`, named `<infohash>.fastresume`.

| Key | What it holds |
|---|---|
| `save_path` | absolute path, **backslashes** on Windows |
| `qBt-savePath` | the same path with **forward slashes** — qBittorrent's own copy, and the two must agree |
| `mapped_files` | one relative path per file, in the torrent's file order; present only once a file was renamed |
| `pieces` | **one byte per piece**, `1` = have, so a complete torrent is `b"\x01" * (len(info[b"pieces"]) // 20)` |
| `qBt-name` | the display name in the list, independent of `info["name"]` |
| `file_priority` | one entry per file, so it needs resizing alongside `mapped_files` |

- **Edits need the application stopped**, since it rewrites every `.fastresume` from memory on exit.
- **Round-trip every file before trusting the encoder.** An encoder that reproduces all of `BT_backup` byte-identically is the cheap proof that a rewrite changes only the key you meant; Python dicts preserve insertion order, so decode-then-encode is faithful without sorting keys.
- **Verify a remapping by piece hash, never by file size.** Sizes are what got you here — they match by construction, since size is how the candidates were found. Read the piece containing the start of each file and compare its SHA1 against `info["pieces"]`. Then prove the check can fail: swap two files in the mapping and confirm it reports a mismatch.
- **Match by size against an index of the whole library, then anchor on a directory.** Scanning global candidates for every file is quadratic and degenerates on a game repack with thousands of files, where zero-length and small files share sizes — one such run burned 21 minutes of CPU for 0.3 GB read. Take the largest file's matches, walk up as many levels as its relative path is deep to get the implied root, and match the rest only under that root, preferring an exact relative path, then a basename, then a size.
- **A rejected resume is the benign failure**: libtorrent rechecks against `mapped_files` and finds the data, so a wrong `pieces` costs a recheck rather than a re-download. A wrong *mapping* is the expensive one, which is why the hash check is not optional.
- **Confirm afterwards that nothing downloaded** — the process's write counter still at zero, no `*.!qB` files, no file under the target modified. `Restored torrent` in `logs/qbittorrent.log` with no matching `Failed to restore torrent` for the same name is what says the resume was accepted.
- **Count the failures across log rotations before calling a repair an improvement.** One startup's warnings can straddle `qbittorrent.log` and `qbittorrent.log.bak1`, so a tail of the current file reports a fraction of them and the before/after comparison flatters itself.

## Exporting the `.torrent`: `GET /api/v2/torrents/export?hash=<torrent ID>`

- Answers the torrent file once metadata exists; before that, HTTP 409 with "Missing metadata". A magnet-added torrent has metadata by the time it finishes.
- The export carries the torrent's current tracker list, including a magnet's `tr=` trackers, and none of the original file's comment.
