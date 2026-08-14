# Keyboard seeking in a browser's native `<video controls>`

Native controls are a good default — they bring scrubbing, volume, fullscreen, PiP and captions for nothing — but their
keyboard map is neither fixed nor consistent between browsers, and it cannot be configured. `<video>` exposes no
attribute for the seek step. If a predictable interval matters, bind your own keys.

## Chrome/Edge: an arrow press is 1% of the runtime, not a number of seconds

Blink does not seek on arrow keys at all. `MediaControlsImpl::DefaultEventHandler` forwards them to the timeline
element, and the seek amount falls out of that slider's stepping rules:

- the timeline is an `<input type=range>` with `min=0` and `max=duration` (`media_control_timeline_element.cc`);
- its base class sets `step="any"` (`media_control_slider_element.cc`, in the constructor — easy to miss, since the
  timeline itself never mentions `step`);
- `RangeInputType::HandleKeydownEvent` treats `step="any"` as `(max − min) / 100`, and `PageUp`/`PageDown` as
  `big_step` = `max((max − min) / 10, step)`.

| key | effect |
|---|---|
| `←` / `→` | ±1% of the runtime |
| `PageUp` / `PageDown` | ±10% of the runtime |
| `Home` / `End` | start / end |
| `↑` / `↓` | volume ±5% (the controls send five slider steps per press) |
| `Space` / `Enter` | play-pause |
| double-tap the left/right half (touch) | ∓10 s — `kNumberOfSecondsToJump`, the one fixed constant, and not on the keyboard |

So the same press is ~25 s in a 42-minute episode and ~72 s in a two-hour film. Reports that "Chrome skips 10 seconds
or so" are people measuring one video and generalising.

Every key above only fires while the video or its controls have focus, which on a page full of other controls takes an
indeterminate number of tabs to reach — a long-standing complaint of its own.

## Firefox: a flat 5 s

`toolkit/content/widgets/videocontrols.js` maps `ArrowLeft`/`ArrowRight` to a fixed 5-second seek and `accel`-arrow
(Ctrl/Cmd) to 10% of the runtime. Duration-proportional versus fixed is a real behavioural fork, not a rounding
difference — do not describe "the arrow keys" to a user as though they mean one thing.

## Verifying this yourself

Chromium's code search UI does not fetch usefully, but the GitHub mirrors do, so `curl` + `grep` answers these
questions in one call:

```bash
curl -sL https://raw.githubusercontent.com/chromium/chromium/main/third_party/blink/renderer/\
modules/media_controls/media_controls_impl.cc | grep -n "kArrowLeft" -A4
```

The four files that decide the whole map:

- `third_party/blink/renderer/modules/media_controls/media_controls_impl.cc` — which key goes where
- `.../media_controls/elements/media_control_timeline_element.cc` — `min`/`max` from the duration
- `.../media_controls/elements/media_control_slider_element.cc` — the `step="any"` that makes it proportional
- `third_party/blink/renderer/core/html/forms/range_input_type.cc` — what `step="any"` means to a keypress

and, for Gecko, `toolkit/content/widgets/videocontrols.js` in `mozilla/gecko-dev`.

## Rolling your own step

Three things bite when you write the seek yourself:

```js
if (!video || video.readyState < HTMLMediaElement.HAVE_METADATA) return;
const to = video.currentTime + seconds;
video.currentTime = Math.max(0, Number.isFinite(video.duration) ? Math.min(to, video.duration) : to);
```

- **Before `loadedmetadata` the assignment is silently dropped** — there is nothing to seek within yet — and in a
  player that also seeks to a stored resume point, both writes race the same event.
- **`duration` is not always a number.** An HLS stream reports `Infinity` when the player reads the playlist as live,
  and `Math.min(x, Infinity)` is fine while `Math.min(x, NaN)` is `NaN`, which puts the seek nowhere.
- **A negative `currentTime` is rejected**, so the lower clamp is not cosmetic.

Seeking to exactly `duration` fires `ended`, which in an app that reports watch state on `ended` counts the play as
finished. That is usually right for someone skipping the last credits, but it is a decision, not a detail.

Binding `A`/`D` (or `J`/`L`) rather than the arrows leaves the native map intact underneath, so both the proportional
jump and the fixed one are available. Match on `e.key` and a non-Latin layout stops the shortcut working (`ф`/`в` on a
Russian layout); match on `e.code` and it becomes positional, which is right for a `WASD`-style pair and wrong for a
mnemonic like `S` for subtitles on Dvorak. Pick per key, deliberately.
