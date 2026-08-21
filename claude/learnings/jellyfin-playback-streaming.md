# Jellyfin API — streaming a film into your own browser player

How to negotiate, stream, subtitle and tear down Jellyfin playback from a third-party web app, instead of deep-linking
to Jellyfin's own web client. Verified live against **Jellyfin 10.11.11**. The companion file
`jellyfin-watch-state-api.md` covers reading a library and writing played state; this one is only about playback.

## Auth: migrate off X-Emby-Token now

Send `Authorization: MediaBrowser Token="<key>", Client="…", Device="…", DeviceId="…", Version="…"`.

- 10.11 added an `EnableLegacyAuthorization` switch; **10.12 defaults it off**, ~10.13 removes the legacy methods
  entirely. Legacy set: `X-Emby-Token`, `X-MediaBrowser-Token`, `X-Emby-Authorization`, `api_key=`. Survivors: the
  `MediaBrowser` header and the `ApiKey=` query param (capital A, capital K).
- Only `Token` is actually validated. Verified: a stale `Version`, an omitted `Version`, extra unknown fields,
  reordered fields, a different `Client`/`Device`/`DeviceId`, even a fully unquoted header — all return 200. Only a
  bad or absent token gives 401. So drift between two copies of the header cannot 401 anything.
- **Under a server API key, Jellyfin overwrites the identity fields** with its own defaults (`Client` = the API key's
  name, `DeviceId` = the server's SystemId), so every API-key caller collapses into one session and you cannot brand
  yourself in Dashboard → Devices.
- **But the DeviceId you send still reaches the transcode job.** It comes back stamped on the `TranscodingUrl`, and
  that is what teardown matches on. Send a stable per-browser id, or two viewers share one job and each other's stop.

## PlaybackInfo: always send a real DeviceProfile

`POST /Items/{itemId}/PlaybackInfo?userId=…` with a body of `{UserId, DeviceProfile, MaxStreamingBitrate,
StartTimeTicks, AudioStreamIndex, EnableDirectPlay, EnableDirectStream, EnableTranscoding, AllowVideoStreamCopy,
AllowAudioStreamCopy, AutoOpenLiveStream}`.

- **Without a profile it claims `SupportsDirectPlay: true` for everything** — including files the browser cannot
  decode. The profile is what makes the answer meaningful.
- Response: `MediaSources[]` with `SupportsDirectPlay/DirectStream/Transcoding`, `TranscodingUrl`,
  `TranscodingSubProtocol` (`hls` | `http`), `Container`, `ETag`, `RunTimeTicks`, `MediaStreams`, plus a
  `PlaySessionId`. There is **no `DirectStreamUrl` field** — build the direct URL yourself.
- `MaxStreamingBitrate` on the request **overrides** the profile's own value (verified: profile 8 Mbps + override
  20 Mbps negotiates at 20). Don't maintain both knobs.
- Changing the audio track is a **re-negotiation**, not a player setting: re-POST with `AudioStreamIndex`, get a new
  `PlaySessionId` and URL, reload, seek back. The master playlist is single-variant with no `EXT-X-MEDIA`, so hls.js
  exposes no alternate audio to switch between. **But see the next section — the index alone does nothing.**

### `AudioStreamIndex` is ignored unless `MediaSourceId` comes with it

The index on its own is **silently dropped**: 200, a valid stream, and the file's default track every time. The
picker moves and the sound doesn't. Verified on a 4-track episode, asking for each track in turn:

```
                                          DefaultAudioStreamIndex   AudioStreamIndex in TranscodingUrl
no request                                          1                            1
body  AudioStreamIndex=3                            1                            1   ← dropped
query audioStreamIndex=3                            1                            1   ← dropped
body  AudioStreamIndex=3 + MediaSourceId            3                            3   ✓
query audioStreamIndex=3 + mediaSourceId            3                            3   ✓
```

Placement is irrelevant — body and query behave identically — the **pairing** is what matters. Unnamed, the request
is about the *item*, and an item has no audio tracks; its media sources do. Take `MediaSourceId` from
`MediaSources[].Id` of the first negotiation and hand it back with every re-negotiation. Expect the same of
`SubtitleStreamIndex`.

Make the two inseparable in your own wrapper — one `audio?: {streamIndex, mediaSourceId}` option rather than two
independent optional parameters. There is no error to catch here, so a caller that forgets the source gets a
plausible stream and a bug nobody notices until they listen.

### Never advertise Matroska for direct play

Chrome answers `canPlayType('video/x-matroska; codecs="avc1.640028, mp4a.40.2"')` = `"probably"` and then **stalls at
0 ms**: `loadstart`, then `stalled`, `readyState` 0, and **no error event ever fires**. Jellyfin's own web client
hard-codes the same exclusion for Chrome. Keep `mkv` out of `DirectPlayProfiles` whatever the browser claims; those
files go down the HLS path, where the video is usually stream-copied and only the audio is re-encoded.

The practical blocker for a typical library is rarely the video codec — it's the container plus AC-3/E-AC-3/DTS
audio, which no desktop browser decodes (Chromium has the code behind a Dolby build flag that ships off).

### HEVC in `TranscodingProfiles` decides copy vs re-encode

Probe the machine (`MediaSource.isTypeSupported('video/mp4; codecs="hvc1.1.6.L93.B0"')`) and include `hevc` in the
transcoding profile's `VideoCodec` when supported. Verified on a 10-bit HEVC film:

```
hevc absent  → TranscodeReasons=ContainerNotSupported,VideoCodecNotSupported,AudioChannelsNotSupported
hevc present → TranscodeReasons=ContainerNotSupported,AudioChannelsNotSupported
```

`VideoCodecNotSupported` disappearing is the difference between a remux and a full software x264 encode. HEVC is
hardware-gated with no software fallback in Chrome, so it is a property of the GPU/driver — probe per device, never
cache the answer server-side.

## Use TranscodingUrl verbatim

The server builds it, quirks included: lowercase `/videos/`, the **dashed-GUID** form of the item id, a leading `?&`
(empty first parameter), unencoded commas in codec lists, and keys like `h264-level`. Re-serialising through
`URLSearchParams` "fixes" those and breaks playback. Strip parameters by splitting on `&` and rejoining.

Item ids need normalising for comparison: the API returns **32-hex** ids, every playback URL uses the **dashed GUID**
of the same id.

Two other shapes:
- Direct play: `/Videos/{itemId}/stream.{container}?Static=true&mediaSourceId=…&Tag={ETag}` — honours HTTP Range
  (206 + `Content-Range`), so real seeking.
- Progressive transcode (`stream.mp4` without `static`) returns **`Accept-Ranges: none`** and chunked encoding —
  playable but **unseekable**. Only the HLS path gives a working scrubber.

`GET /Videos/{id}/stream` is declared `[AllowAnonymous]` in the 10.11 spec — verified 206 with no credentials at all.
Anyone who can reach the host can download any item by GUID. Treat that as an upstream gap you tolerate, not a
contract; `master.m3u8` correctly 401s without a token.

## The token only lands in playlists if your request used a query token

This one decides whether you need a playlist rewriter. Jellyfin propagates **whichever auth mechanism the request
used** into the child URLs it generates:

| request auth | tokens inside a 2-hour film's media playlist |
|---|---|
| `?ApiKey=…` query param | **835** |
| `Authorization: MediaBrowser` header | **0** |

So a proxy that authenticates by header gets clean manifests for free. What *does* always arrive with a token baked
in is `MediaSources[].TranscodingUrl` and every subtitle `DeliveryUrl` — strip those yourself.

## Subtitles

- `MediaStreams[]` with `DeliveryMethod: "External"` carry a ready-made `DeliveryUrl`; swap the extension to `.vtt`
  and the server converts server-side (`text/vtt`, no auth needed, ~5 ms). Render as plain `<track>`.
- `DeliveryMethod: "Encode"` means burn-in — image formats (PGSSUB/DVDSUB/VOBSUB) can never be anything else, and
  Jellyfin also refuses ASS→VTT.
- **The burn-in trap.** `SubtitleProfiles` in your DeviceProfile constrains how a track may be *delivered*, **not
  which track the server selects**. If the user's default subtitle is unconvertible, Jellyfin picks it anyway and
  resolves the conflict by burning it in — the `TranscodingUrl` comes back with
  `SubtitleStreamIndex=N&SubtitleMethod=Encode`, and a stream that would have been `-codec:v:0 copy` becomes
  `libx264 … -vf "…,subtitles=…"`. On a box without hardware acceleration the first segment may never arrive.
  **Fix: drop `SubtitleStreamIndex` and `SubtitleMethod` from the URL when `SubtitleMethod=Encode`.** Verified — the
  same title then logs `DirectStream` with `-codec:v:0 copy` and a first segment in ~0.2 s.
  Passing `SubtitleStreamIndex: -1` in the body **or** the query does **not** work. Declaring `ass` as `External`
  also clears the burn-in, but the track then arrives as `Stream.ass`, which no browser renders.
- `DefaultSubtitleStreamIndex` can name a track absent from your side-loadable list (because it's `Encode`-only) —
  a naive `find(s => s.index === defaultSubtitleIndex)` returns undefined.

## Which track is "default" is a per-USER setting — there is none per item

Verified against 10.11.11 by reading the server's own spec (`/api-docs/openapi.json`; `/openapi.json` 404s). Nothing
sets a default audio or subtitle track on a movie or show: `UserItemDataDto` carries only `PlaybackPositionTicks`,
`PlayCount`, `Played`, `IsFavorite`, `Rating`; the per-item subtitle endpoints fetch or download files; and
`POST /Items/{itemId}` takes a `BaseItemDto` whose only track-related fields (`HasSubtitles`, `MediaStreams`,
`Audio`) are read-only reflections of the file. The `IsDefault` flag is the container's own disposition.

What exists is one global preference per user — `POST /Users/Configuration?userId=<id>`:

| field | |
|---|---|
| `AudioLanguagePreference` | one language, ISO 639-2 (`"eng"`) |
| `SubtitleLanguagePreference` | one language |
| `SubtitleMode` | `Default` / `Always` / `OnlyForced` / `None` / `Smart` |
| `PlayDefaultAudioTrack` | bool |
| `RememberAudioSelections`, `RememberSubtitleSelections` | bool |

Two traps:

- **`PlayDefaultAudioTrack: true` makes `AudioLanguagePreference` inert.** It is the UI's "play default audio track
  regardless of language". Set it false, or the language preference does nothing at all.
- **The endpoint replaces the whole object.** Read the user's current `Configuration` from `GET /Users`, spread it,
  and post it back with only your fields changed — otherwise every other setting silently resets.

These feed `DefaultAudioStreamIndex` / `DefaultSubtitleStreamIndex` in the PlaybackInfo response, which is why they
matter to a client that picks its own tracks: with the preference set, the server's FIRST answer is already the one
you want, so there is no second negotiation. Measured on a library of English films carrying Russian dubs (the dub
flagged default in the file): items needing a second `PlaybackInfo` fell from **437 to 10**. The residue is the real
limit of the mechanism — one global language cannot express "whatever this title's original language is", so a
client that wants the original still has to retune for foreign-language titles.

## HLS shape and seeking

- `master.m3u8` is a tiny variant index (~700 B) pointing at a relative `main.m3u8`.
- `main.m3u8` is a **complete VOD playlist with `EXT-X-ENDLIST`, generated instantly** from `RunTimeTicks` — ffmpeg
  has not started yet. The player sees full duration and a seekable range immediately.
- `segmentContainer=mp4` → fMP4/CMAF (`EXT-X-VERSION:7` + `EXT-X-MAP` init segment at index `-1`); `ts` → MPEG-TS.
- **Seeking is just requesting a different segment index.** `startTimeTicks` does **not** shift the playlist —
  verified byte-identical with and without it. Set `video.currentTime`; Jellyfin repositions ffmpeg. Cold seek TTFB
  ~0.5 s, then ~0.1 s; already-written segments persist on disk and re-serve in ~0.2 s.
- Omitting `audioCodec` from a hand-built URL makes the server infer it from the path extension and emit
  `AudioCodec=m3u8` — a video-only stream. Another reason to use the server's URL as-is.

## Teardown is not optional

`DELETE /Videos/ActiveEncodings?deviceId=…&playSessionId=…` (both required; missing `playSessionId` → 400).

- Returns **204 for ids that never existed** and for repeat calls, so success proves nothing — verify via
  `GET /Sessions` and its `TranscodingInfo`.
- With `EnableThrottling` and `EnableSegmentDeletion` both off (the default), **nothing paces ffmpeg to the player**:
  one Play click writes the entire remuxed film to the transcode cache within a minute or two (measured 2.4 GB in
  40 s; 48 segments within 2.5 s of the first segment request). Every abandoned play that misses teardown leaves a
  film-sized directory behind. A successful teardown removes that job's own segments.
- Call it from `pagehide` with `fetch(…, {keepalive: true})` — a Server Action cannot be sent that way, which is why
  teardown wants to be a plain route.
- `POST /Sessions/Playing/Ping?playSessionId=` keeps a job from being reaped during a long pause.

## Proxying it through your own origin

Serving media from your own app rather than the media server buys three things at once: the credential never reaches
the browser, a plain-HTTP server on a private address stops being blocked as mixed content on an https page, and
there is no CORS to arrange (Jellyfin's default `CorsHosts` is `["*"]`, but a literal `*` also forbids credentialed
requests).

- **Child URLs inside a playlist are relative** (`main.m3u8?…`, `hls1/main/0.mp4?…`). Mirror the upstream path shape
  under your proxy and they resolve back through it with **zero rewriting**.
- **If you rewrite a playlist body, recompute `Content-Length`.** Stripping tokens shortened one real playlist by
  33,400 bytes; forwarding the upstream length makes the player hang waiting for bytes that never arrive. Also don't
  forward `Content-Encoding` — undici has already decompressed.
- Forward the inbound `Range` header and the request's abort signal; hls.js cancels in-flight fragment loads on every
  seek. Do the body read inside the same try as the fetch — an abort after headers but before the body rejects
  separately.
- Allowlist the upstream path root (`videos`) **case-insensitively**: `TranscodingUrl` is lowercase `/videos/`, while
  subtitle `DeliveryUrl` and direct-play URLs use capital `/Videos/`.
- Check the item id in the path against your own records before forwarding, or an allowlist alone turns the endpoint
  into a credential-attaching passthrough for the whole library.

## Reporting playback is a silent no-op under an API key

`POST /Sessions/Playing`, `/Progress`, `/Stopped` all return 204 and **write nothing** when authenticated with a
server API key: the session's `UserId` is the all-zero GUID, so the server iterates zero users. Use the explicit
`?userId=`-taking endpoints instead (`/UserItems/{id}/UserData`, `/UserPlayedItems/{id}`) — an API key carries the
Administrator role, which is what makes those accept another user's id.

## Telling real playback from a stalled player, from the server log alone

You often cannot see the picture — a headless/automation tab won't autoplay, and screenshots may be unavailable. The
segment request pattern tells you anyway, because hls.js only fetches while its forward buffer is short of target:

```
getMaxBufferLength = min(max(8 * 60e6 / BANDWIDTH, 30), 600)     // hls.js ~1.6, dist/hls.js
```

`BANDWIDTH` is declared in the master playlist. For a 5,582,788 bps remux that is **86 s**, and with 10 s segments a
playhead **pinned at 0** fetches exactly `-1, 0 … 9` and then stops (buffered 95.08 s > 86 s). So:

| pattern in the log | meaning |
|---|---|
| a run of ~N fragments then silence, N ≈ target/segment | the element is PAUSED — buffer filled, playhead never moved |
| fragments continuing 10, 11, 12 … at roughly segment-duration intervals | genuine playback |
| a run, then a jump to a distant index, then another run | a SEEK (scrubbing), not playing |

Group them by `PlaySessionId` — one line per play:

```bash
grep -o 'hls1/main/[0-9-]*\.mp4?[^ ]*PlaySessionId=[a-f0-9]*' dev-server.log   | sed -E 's|hls1/main/([0-9-]+)\.mp4.*PlaySessionId=([a-f0-9]+)| |'   | sort -k1,1 -k2,2n | awk '{s[$1]=s[$1]" "$2} END{for(k in s) print k":"s[k]}'
```

This settled a multi-day misdiagnosis: runs of exactly ten fragments with jumps and no continuation proved the
viewer had been scrubbing, never watching — so "no progress was ever reported" was correct behaviour, not a bug in
the reporting code. Reach for it before theorising about the client.


## Letting the BROWSER fetch the stream (instead of proxying it)

Proxying every byte through your own origin is the safe default, but it is the wrong shape once your app is hosted
somewhere the media isn't: the server pulls the film across the internet and pushes it back, so a viewer sitting
next to the media server pays for two traversals of their own uplink. Pointing the player straight at Jellyfin
removes both. Measured on Jellyfin **10.11.11**.

**Jellyfin is already CORS-open**, so cross-origin fetching needs nothing on the server:

```
GET  /System/Info/Public        → access-control-allow-origin: *
OPTIONS /Videos/{id}/stream     → 204, access-control-allow-headers: authorization,range
                                       access-control-allow-methods: GET
```

**Only some of the player can carry a credential.** This is what decides the design:

| what fetches it | can send a header? | so the credential goes |
|---|---|---|
| hls.js (manifest + segments) | yes — `xhrSetup` | in the `Authorization` header |
| `<video src>` (direct play) | no | `?api_key=` on that one URL |
| `<track>` (subtitles) | no | nowhere — keep these on your own proxy |
| native HLS, no MSE (older iOS Safari) | no | nowhere — fall back to the proxy |

```js
new Hls({ xhrSetup: (xhr) => xhr.setRequestHeader("Authorization", mediaBrowserAuth) })
```

The header route matters for more than tidiness: per the section above, a query-authenticated manifest request
comes back with the token stamped into every child URL. Header auth keeps it out of all of them — verified, 0
occurrences in a real transcode manifest. Subtitles are a few hundred KB, so leaving them same-origin costs
nothing and avoids both a second credential-bearing URL and the `crossorigin` attribute entirely.

### Credentials: an API key is not the scoped option

**Every Jellyfin API key is admin-equivalent** — there is no scoping. The credential a *page* holds should instead
be a **user access token** from `POST /Users/AuthenticateByName` (needs the `Authorization: MediaBrowser Client=…,
Device=…, DeviceId=…` header on the request itself). Create a dedicated account for it: `POST /Users/New`, then
`POST /Users/{id}/Policy` with `IsHidden: true`, `IsAdministrator: false`, `EnableContentDeletion: false`,
`EnableContentDownloading: false`, `EnableAllFolders: true`, and the three playback/transcoding flags left on.
Start from the policy the server generated (`GET /Users` → `.Policy`) and mutate it; posting a hand-built policy
drops required fields.

What such a token can and cannot do, verified against a real server:

| call | result |
|---|---|
| `GET /Videos/{id}/master.m3u8`, segments, subtitles | 200 |
| `GET /Auth/Keys` | **403** |
| `POST /UserItems/{item}/UserData?userId=<other user>` | **403** |
| `GET /Users`, `GET /System/Info`, `GET /Sessions` | 200 — but filtered to itself for Sessions |

That last row is the reason to bother: a token scoped to a *user* who happens to be the one you sync can still
rewrite the watch history your app curates. A stream-only account cannot. And the exposure is real even on an
owner-only page — an `httpOnly` session cookie is unreadable by page JS, while this token must be readable to be
attached to a request, so XSS or a hostile extension reaches one and not the other.

### Credentials do not have to match across a play

Negotiating with one credential and streaming with another works, which is what lets the server keep its admin key
while the browser holds a scoped one:

- `PlaybackInfo` requested with the API key; the returned `TranscodingUrl` fetched with the user token → 200.
- The transcode that starts is then **torn down by the API key**: `DELETE /Videos/ActiveEncodings?deviceId=…&
  playSessionId=…` → 204, `ffmpeg` count 1 → 0. Teardown keys on the ids, not on who started the job.

### Streaming alone writes no watch state

A stream request creates **no** `NowPlayingItem` session (`GET /Sessions` stayed empty while a 4.4 MB segment was
being served) and moves no `UserData`. Watch state only moves when a client explicitly reports it. So the account
whose token fetches the bytes never accumulates history, and there is nothing to reconcile between it and the
account your app reports progress for.

### Small 10.11 API notes

- `GET /Users/{userId}/Items/{itemId}` is gone — returns an empty body. Use `GET /Items?userId=…&ids=…`.
- `GET /Users/Me` answers 400 even with valid auth; `/System/Info` is a better auth smoke test (401 unauthenticated).
- `POST /Auth/Keys?App=<name>` returns 204 with no body — list `GET /Auth/Keys` afterwards to find what was made.
