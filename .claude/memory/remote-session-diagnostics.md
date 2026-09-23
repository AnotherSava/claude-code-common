---
name: remote-session-diagnostics
description: "\"my remote session didn't connect\" means the tmux feature in claude/remote-session, not Claude Code's Remote Control — and the four commands that read its live state"
metadata:
  type: project
---

A "remote session" in this repo is `claude/remote-session/`: the Windows machine's Claude session held
in a WSL tmux server, opened from the Mac with **cmd+shift+r** in agterm. Its own README is the
reference; this file is how to find out what is actually happening right now, which the README does
not cover.

It is **not** Claude Code's Remote Control, and not a claude.ai cloud session. Those are separately
disabled by `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` on both machines — see
[[essential-traffic-hides-gated-commands]] — so diagnosing a complaint as that one is almost always
diagnosing the wrong feature. Ask which they mean before spending a probe on either.

## Reading the live state

Take the coordinates from the config rather than hardcoding them; it is transcrypt-encrypted and its
keys are the ssh host and user, the distro, the projects root and the path to `claude.exe`:

```sh
cd claude/remote-session && . ./lib.sh && remote_session_load_config ./config.secret.env
```

Four commands answered every question in the 2026-09-22 diagnosis:

- `curl -s http://127.0.0.1:9077/api/agents` — whether a session for that project exists on the
  Windows device at all, with its status and label. Remote rows are namespaced (`CHROME/<project>`);
  [[peer_messaging]] has what the fields are worth.
- `ssh "$REMOTE_USER@$REMOTE_HOST" "wsl -d $WSL_DISTRO -- tmux ls"` — the attachable sessions, and
  **when each was created**. That timestamp is what separates "the attach joined something already
  running" from "the attach created it", which no other source answers.
- `ssh … "wsl -d $WSL_DISTRO -- tmux capture-pane -p -t <session>"` — what is on that session's
  screen. Pass the **bare** name here: the `=name` exact-match form the scripts use for
  `has-session` is rejected by `capture-pane` as `can't find pane`, which reads as a dead session.
  `display-message -p -t` refuses it the same way, and worse — it prints an empty value and exits 0,
  so a format like `#{pane_dead}` comes back blank and a caller testing it for `1` silently decides
  the pane is alive. Both took the bare name; `has-session` and `kill-session` keep the `=`.
- The Windows box's conversation files, under that profile's `.claude/projects/`, in a directory
  named from the project's full path with separators flattened (`D--projects-<name>`). Listing it by
  mtime shows whether a conversation existed before the session started, and whether a second one
  now exists beside it.

Everything above is read-only. Killing or restarting a remote session ends a live agent's turn, so
it is the user's call, not a diagnostic step.

## "It didn't connect" is two different complaints

The tmux session and the conversation inside it are separate things, and the phrase fits either:

- **No tmux session was joined.** Only a session inside the holder's server is attachable. A Claude
  started some other way owns its own pty and cannot be joined by anything; the picker omits it
  rather than offering what it cannot do. `_holder`'s own creation time bounds this — sessions do
  not survive the holder, so nothing older than that row can still exist.
- **The tmux session was fine and the conversation was new.** This is the one that misleads, because
  the attach genuinely worked and the screen is genuinely empty.

The second was a real defect, found and fixed 2026-09-22: `cc-session.sh` launched `claude.exe`
bare, while `start-here.sh` — the Windows machine's `claude` function — resumed with `--continue`.
So the same project came back to its old conversation when opened on Windows and started a blank one
when opened from the Mac. Both now build the command through `remote_session_resume_command` in
`lib.sh`. Worth knowing the shape rather than the incident: two entry points to one feature, one of
them quietly doing less.

## A version skew between the two checkouts reads as a usage error

Both machines run the same scripts out of their own checkout of this repo, so the halves can be at
different commits, and the interface between them has changed under that. `cc-session.sh` takes a
second argument since 2026-09-22 — the machine whose keyboard the person is at — and refuses
without it, so a Mac whose checkout predates that pushes one argument and gets the usage line back.

Nothing in that message says "your checkout is behind", which is why it belongs here. Before
reading an attach failure as a broken feature, compare what each side is running:

```sh
git log --oneline -1 -- claude/remote-session
ssh "$REMOTE_USER@$REMOTE_HOST" "wsl -d $WSL_DISTRO -- git -C $REPO_WSL_PATH log --oneline -1 -- claude/remote-session"
```

Pull on whichever is behind. The repair is the same whichever direction the skew runs in, and the
next change to that interface will present exactly the same way.
