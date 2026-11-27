# Memory growth from what a native host pushes into its webviews

A desktop app that pushes state into a webview on every change pays for each push in the **host** process, not only in the page. A Tauri `emit` becomes one script evaluation per webview with a listener, and on macOS the host keeps each payload copy until WebKit has delivered it. Ship a large snapshot often enough and both sides grow: the host holds the copies waiting for delivery, and the WebContent processes hold what they parsed.

## How it showed up

A Tauri dashboard on macOS reached 25 GB after 17 hours, swapped the disk full, and freed most of it on relaunch. Over a day the webviews held more than the host: at 17 hours its two WebContent processes showed 1.4 GB and 1.36 GB in memory with 10 GB and 16 GB compressed, and an earlier reading showed 25 GB compressed across the two. Ten minutes after a launch the same webviews held under 300 MB each, so a short sample shows only the host's half. Reading swap and finding the process that holds it is in the swap bullet of `skills/broom/SKILL.md`. Every `sessions_updated` emit carried every row's full conversation history, about 10 MB, to two listening webviews: the main widget and a history window that stayed hidden most of the time. The widget drew none of that text.

## Find it

1. **Split the host from the webviews.** Run `footprint <pid>` on the app and on each `com.apple.WebKit.WebContent` process started within a second of it. Here the host's `Malloc Large` category held almost everything (1.2 GB ten minutes after launch) while each WebContent process held under 300 MB.
2. **Sample the growing category once a second.** Run `footprint <pid> | grep 'Malloc Large'` in a loop and print the size and region count. Here it rose in steps of about five regions (25–50 MB) and fell back in bursts as WebKit delivered the copies. A sawtooth like that, rather than a smooth climb, points at large allocations being held and released, not at a leak in the usual sense.
3. **Line the steps up against the app's own log.** Each step fell within a second of a frontend `sessions_updated` trace line in the app's JSON log. Five regions per step fit one serialized payload plus two script copies for each of the two listening webviews.

## Fix it

- **Send each webview only what it draws.** Strip the bulky field from the pushed rows and replace it with a cheap fingerprint of its contents. The dashboard sends `dialog_rev`, a hash over each entry's timestamp, role, text length and text tail.
- **Let the one view that needs the bulk pull it on demand.** The history window calls a command for its single session's dialog, and only when that row's fingerprint moves.
- **Check a hidden window's listeners.** A pre-created hidden window that registers a listener at mount receives every push for the life of the process.

After the fix the host held at 150–225 MB for the first five minutes. At 27 minutes it still ran a sawtooth: top's MEM swung between 153 MB and 785 MB, with `Malloc Large` peaking at 622 MB and draining to 32 MB. So the growth is bounded, but something still pushes payloads large enough to stack up. In the dashboard the likeliest remaining one is each row's tooltip task list, every task prompt in the row's history (about 1.5 MB across the live rows), which the fix commit (b9da3b9 in the dashboard repo) also caps at the five the tooltip draws. The cap went into that commit after the measured build had been deployed from the working tree, so these readings predate it and it is not yet confirmed as the rest of the cause.

## On Windows

WebView2 behaves the same way. It runs the page in `msedgewebview2.exe` processes. Before the fix, the dashboard's WebView2 processes held 4.3 GB of private memory four hours after launch, two renderers at about 2 GB each.

**Measure it per process, not as a total.** Select the `msedgewebview2.exe` processes whose command line names the app, and read each one's type off its own command line. A browser-wide total hides which process grows and mixes in other apps' WebView2 instances. The app's own `.exe` is a separate process; leave it out of the WebView2 sum and report it beside it.

```powershell
$wv = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq "msedgewebview2.exe" -and $_.CommandLine -like "*{{app-exe-name}}*" }
foreach ($p in $wv) {
  $t = if ($p.CommandLine -match '--type=(\S+)') { $Matches[1] } else { 'browser' }
  "{0} {1} private={2}MB" -f $p.ProcessId, $t, [math]::Round($p.PrivatePageCount/1MB)
}
```

The `PrivatePageCount` field is the process's committed private memory, the figure that grows with a leak. The working set rises and falls with what Windows trims, so it misleads on a trend.

**Take a day of readings before calling growth a leak.** After the fix the WebView2 total went from 278 MB at launch to 357 MB at three hours and 421 MB at 15.7 hours. That looked like unbounded growth, about 9 MB an hour across the span, though most of it came in the first three hours. Then the largest renderer fell from 114 MB to 52 MB within the next hour, and over six hourly readings to 23 hours the total held between 358 and 375 MB. A renderer giving memory back in one step is garbage collection catching up, and a leak never does that. The readings were taken with the user away and the widget barely updating, so a day of active use was not covered.

## Remaining limits

- Why WebKit delivered in batches, and whether a hidden window's deliveries ever stall completely, was not measured.
- The webviews' day-scale growth after the fix was not measured on macOS. Check it with `footprint` on each WebContent process after a day of uptime, not ten minutes after a launch.
