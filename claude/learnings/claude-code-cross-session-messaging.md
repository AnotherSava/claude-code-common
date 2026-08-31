# Claude Code cross-session messaging (agent ↔ agent)

Claude Code sessions can message each other natively. Documented at
`code.claude.com/docs/en/cross-session-messaging.md`. Everything below was verified on macOS against
2.1.238 and 2.1.251 on 2026-08-30, mostly by probing throwaway sessions rather than from the docs.

Before designing any agent-to-agent messaging scheme, check this first — a whole class of
keystroke-injection workarounds (typing into a terminal pane, reading the pane back to confirm) is
obsoleted by it.

## What it is

- `ListAgents` — lists reachable peers. A normal loaded tool.
- `SendMessage` — delivers plain text to one by name. **Deferred** (`shouldDefer:true`), so the model
  spends one `ToolSearch` before its first send. It is still discoverable: the name appears in the
  deferred list.
- `/list-agents` (alias `/peers`) shows the roster; `/status` shows this session's own inbox as
  `Peer address`; `/rename <name>` and `--name` / `-n` set the name.

The model sends on its own initiative when it judges the need, so a plain-language prompt is enough.
Verified: `Let wtbeta know that the schema migration finished` produced
`ListAgents` → `ToolSearch{select:SendMessage}` → `SendMessage{to:"wtbeta", ...}` with no tool named in
the prompt.

## Enablement — the version cliff that matters

The gate is a statsig flag with a **code default that changed between versions**:

```js
// 2.1.238
function eg(){if(V.CLAUDE_CODE_HARBOR_KITE)return!0;
  if(Wt()==="windows"&&!it("tengu_harbor_kite_win",!1))return!1; return it("tengu_harbor_kite",!1)}
// 2.1.251
function Yo(){let e=a.CLAUDE_CODE_HARBOR_KITE;if(e!==void 0)return Me(e);
  if(D()==="windows"&&!I("tengu_harbor_kite_win",!0))return!1; return I("tengu_harbor_kite",!0)}
```

`!1` → `!0`. Exported as `isCrossSessionMessagingEnabled`.

This interacts with privacy settings in a way that is easy to get backwards. With
`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` (also `DISABLE_TELEMETRY`, `DO_NOT_TRACK`), feature-flag
evaluation is off, so the **code default governs** — which means the feature was off on 2.1.238 and on
by default from 2.1.251, with no settings change either way. Per the docs, same-machine messaging with
flag fetching off needs **2.1.248+**; the general floor is 2.1.224 (macOS/Linux/WSL2) and 2.1.234
(native Windows).

Do not conclude "it's off" from `CLAUDE_CODE_HARBOR_KITE` being unset. The honest tell is
`messagingSocketPath` in the session record. Specifically **not** a tell: the existence of the
`cc-socks` directory — A/B tested, it is created unconditionally, gate or no gate.

## Session registry

Each session writes `<claude-config>/sessions/<pid>.json`:

```json
{"pid":80525,"sessionId":"…","cwd":"…","version":"2.1.251","peerProtocol":1,
 "peerFeatures":["notify_idle","reply_across_default_dirs","artifact_yield"],
 "kind":"interactive","entrypoint":"sdk-cli","pidDomain":"darwin",
 "messagingSocketPath":"/tmp/…/cc-socks/80525.sock",
 "name":"proj-89","nameSource":"derived","status":"idle"}
```

- `nameSource` is `derived` unless `--name`/`/rename` set it, then `user`. **Derived names carry a
  random suffix that changes on every restart** (`landlord-4b` → `landlord-29`), so never persist one
  as an address — re-read `ListAgents` each time.
- `pidDomain` (`darwin`, `win32:<hostname>`, `darwin:<machineId>:<pidNs>`) exists to stop pid aliasing
  across machines or pid namespaces; a foreign-domain record is never treated as a local pid. It is
  evidence that this channel is **not** meant to stretch across machines.

## The socket

Path: `$XDG_RUNTIME_DIR || $CLAUDE_CODE_TMPDIR || /tmp` + `/cc-socks/<pid>.sock`, falling back to a
private `/tmp/cc-socks-<uid>` when the directory can't be accepted. Unix socket on macOS/Linux, **named
pipe on native Windows**.

On Windows the pipe is `\\.\pipe\LOCAL\cc-msg-<32 hex>` — verified on a real Windows session
2026-08-30. **Do not derive this format by reading the client's validator regex**, which was tried and
produced `\\.\pipe\cc-msg-<32 hex>`, missing the `LOCAL\` segment; the generator is constant-folded out
of the macOS build, so only the Windows machine can answer it. Read `messagingSocketPath` out of the
session record rather than constructing the path at all. Beside that record sits
`<pid>.<64 hex>.key`, the connection's auth token — which is why the `sessions/` directory must stay
outside any transcript-capture or log-collection scope.

Anything can write to it — one NDJSON frame, connection closed after:

```json
{"type":"user","uuid":"<uuid>","priority":"next",
 "message":{"role":"user","content":"…"}}
```

- `priority:"next"` queues; `"now"` interrupts — prefer `next`.
- Auth frame `{"type":"auth","token":"<CLAUDE_CODE_MESSAGING_TOKEN>"}` as the **first line**: optional
  on macOS/Linux, **required on native Windows** (the connection is dropped otherwise).
- The connection is closed if a complete line doesn't arrive within 30 s — build the payload first,
  then connect.
- An **idle** session starts a new turn on arrival; mid-turn the message is folded in between tool
  calls, so a running tool is never interrupted. A session with a dialog open defers until it closes.

Hooks and Bash commands get `CLAUDE_CODE_MESSAGING_SOCKET` and `CLAUDE_CODE_MESSAGING_TOKEN` exported,
before any hook runs including `SessionStart` — the clean way for a hook to post back into its own
session.

## A raw writer learns almost nothing — so it cannot claim delivery

If you write to the socket yourself (rather than calling `SendMessage`), you can distinguish exactly two
states. Probed on 2.1.251, macOS:

| probe | result |
|---|---|
| connect to a **dead** session's socket | `ECONNREFUSED` |
| connect to a **live** session's socket | succeeds |
| write a well-formed frame, then read | nothing, no EOF, until you time out |
| write unparseable bytes, then read for 12 s | nothing, no EOF |

*Nothing is listening* and *a listener accepted the bytes*. Parse success, auth, the receiver's admission
control (token bucket, identical-repeat window, queue cap) and the delivered / held / refused verdict are
**all invisible** — because drop receipts are sent as a **separate outbound connection back to the frame's
`from` address**, which a writer that binds no inbox of its own never receives.

So an integrator relaying messages must not report "delivered". The honest vocabulary is *written*, with
the caveat stated: the bytes were accepted, and the receiving agent's acceptance is not observable. A
receipt that says "delivered" for something only written is the classic can't-tell-success-from-never-ran
defect, and here it is guaranteed rather than occasional.

Two consequences worth planning around:

- **Windows is weaker still.** The auth line is required there and a connection whose first line is not
  valid auth is closed *silently*, so on Windows even "written" means only that bytes left you. If you
  cannot produce the key, refuse before connecting rather than write and report success.
- **`from` is the rate-limit key.** The receiver keys admission on `from:${from}` and falls back to
  `pid:${verifiedPeerPid}` only when `from` is `unknown`. A relay that omits `from` therefore collapses
  every message it ever forwards into **one** bucket and one dedupe slot, so one chatty sender starves
  the rest and unrelated senders trip each other's repeat-drop. Setting a distinct synthetic `from` per
  originating agent restores per-sender accounting — but `from` is also the reply address and is
  validated (`^(?:uds|bridge|did):…`), so confirm your scheme is accepted against a live session before
  relying on it.

## The gap that bites integrators: hooks cannot see peer origin

The `UserPromptSubmit` hook fires for a peer message **identically to a typed prompt**. Full payload:

```
session_id, transcript_path, cwd, prompt_id,
permission_mode, hook_event_name, prompt, session_title
```

No origin field, and `prompt` holds the peer's **raw text without Claude Code's framing wrapper**. Any
tool that treats `UserPromptSubmit` as "the user typed something" will attribute a peer's message to the
user — mislabelling the session's task, not merely missing an annotation.

The transcript entry does carry it:

```json
{"type":"user","isMeta":true,"promptId":"<same as the hook's prompt_id>",
 "origin":{"kind":"peer","from":"uds:/…/cc-socks/78380.sock","verifiedPeerPid":78380,
           "msg_id":"…","name":"wtalpha","fromMode":"prompting","body":"…"}}
```

`promptId` == the hook's `prompt_id`, so hook and transcript correlate **deterministically**, not
heuristically. The transcript `content` is the framed form —
`<cross-session-message from-name=… from-mode=…>` plus an anti-laundering preamble — while the hook got
the bare body. A transcript-tailing consumer can therefore recover origin; a hook-only consumer cannot.

## Framing and safety, which you get for free

Claude Code prepends its own preamble: the message came from another session, not the user; it cannot
approve anything or answer a pending permission prompt; the receiver must never change permissions,
`CLAUDE.md` or config because a peer asked; and if a peer says it was denied permission and asks the
receiver to do it instead, refuse — "permission laundering". A slash command inside a message arrives as
inert text.

Observed effect: a receiving agent treated an incoming claim as something to verify against its own
working directory before acting. Sending a **fact** works better than sending an order.

Also free, so don't rebuild it: per-sender rate limiting, identical-repeat dropping in a short window, a
50-message accepted-queue cap, and burst refusal **at the sender** — per the docs, a message loop
between two sessions "stops on its own". Same-machine size cap ≈ 1M chars.

## Inbound policy

`crossSessionInbound` = `accept` | `hold` | `refuse`. Unset means **permission-mode class parity**:
bypass↔bypass and prompting↔prompting deliver; a mismatch is held for approval. `auto`, `acceptEdits`
and `dontAsk` all count as *prompting*. A held message raises an approval dialog in the receiving pane
(expiring per `dialogExpiry`, default 5 min), so a mismatched send costs the user an interruption.

Do not set `accept` casually to "make it work" — it permanently removes the consent gate that protects a
session running with weakened permissions. Under all-prompting sessions the default never holds
anything, so it buys nothing.

## Cross-machine

| Target | Route |
|---|---|
| Same machine | Per-session socket / named pipe, never through Anthropic servers |
| Another of your machines | **Through Anthropic servers**, over that machine's Remote Control connection |
| Claude Code on the web | Through Anthropic servers to the cloud session |

Needs Remote Control connected on both ends and a claude.ai sign-in as active auth (not an API key, not
Bedrock/Vertex/Foundry). `isolatePeerMachines: true` requires explicit approval before any message
leaves the machine. If the sender isn't itself connected, the message still goes but carries no reply
address.

There is **no** peer-to-peer or LAN path: zero `tailscale` strings in the bundle, and the listener is
AF_UNIX / named pipe only. Sessions in different containers, or WSL2 vs native Windows on one box,
cannot reach each other — different home directories, different socket types.

## Dead ends, so they aren't re-investigated

- `RemoteTrigger` — schedules **cloud** routines via the claude.ai CCR API (`/v1/code/triggers`).
  Cannot address a desktop session.
- `CLAUDE_CODE_HARBOR_KITE_CLOUD` — gates *listing* cloud/Remote Control sessions
  (`hasCloudPeerAccess`), not the transport. Needs firstParty provider + org UUID +
  `allow_remote_sessions`.
- "Teammate" — agent-team members inside one session; mailboxes are plain files under
  `<config>/teams/<team>/inboxes/<name>.json`. Not a cross-machine addressee.
- `notify_when_idle` — one-shot "tell me when that session next goes idle", **this machine only**,
  12-hour expiry.
- `claude --resume <id>` of a *live* session — refuses with `No conversation found`.
- MCP `notifications/message`, `resources/updated`, sampling — ignored or `-32601`; a server cannot
  start a turn in an idle session. MCP Channels reported "not currently available".
- Appending to a session's transcript `.jsonl` — no re-reader exists; it does nothing.

## Related

- `claude-code-integration.md` — hook payloads, transcript entry types, state classification.
- `agterm.md` — the keystroke-typing approach this supersedes for Claude ↔ Claude.
