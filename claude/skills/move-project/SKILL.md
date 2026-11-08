---
name: move-project
description: >-
  Move or rename the current project folder without losing the Claude Code data keyed to its old
  path — session logs, memory and subagent history — by working out the new data directory name
  and printing the moves, plus the call that carries the dashboard's data over, for the user to run
  from outside the session.
  TRIGGER when: the user wants to move, rename or relocate the folder of the project they are
  working in, or asks what happens to their session history and memory if they do.
  DO NOT TRIGGER when: renaming the GitHub repository without moving the local folder, moving
  files around inside the project, or creating a new project (that is `github-create`).
allowed-tools: Read, Glob, Bash(pwd:*), Bash(git rev-parse:*), Bash(test -e:*), Bash(test -d:*), Bash(test -L:*), Bash(readlink:*), Bash(ls:*), Bash(grep:*), Bash(uname:*)
---

# Move/Rename Project

Move or rename the current project folder while preserving all associated Claude Code data (session logs, memory, subagent history) and the Claude Code dashboard's data for the project.

## Context
- Current project path: !`pwd -W 2>/dev/null || pwd`
- Platform: !`uname -s`

## Process

1. **Ask for the new location.** If the user didn't provide one as an argument, ask:
   > Where should I move this project? Provide a new folder path (relative or absolute) or just a new name (keeps the same parent directory).

2. **Resolve paths.** Determine:
   - `OLD_PATH`: **Current project path** from Context. It uses `pwd -W` where that exists, because on Git Bash a plain `pwd` yields `/d/work/my-app`, which mangles to `-d-work-my-app` instead of `D--work-my-app` — the reference below says so explicitly, and the wrong key names a directory that does not exist
   - `NEW_PATH`: the target — if the user gave just a name, resolve it relative to the parent of `OLD_PATH`
   - Validate that `NEW_PATH` does not already exist (`test -e "NEW_PATH"`). A case-only rename (`Web` → `web`) is the exception: on Windows and on macOS by default the file system ignores case, so `NEW_PATH` reads as existing because it is `OLD_PATH`; allow it when the two differ only in case

3. **Compute Claude data directory names.** Apply the path-mangling rule documented in `~/.claude/skills/skill/references/claude-project-memory-paths.md` to both `OLD_PATH` and `NEW_PATH` to derive `OLD_KEY` and `NEW_KEY`. That file is the canonical reference for the mangling rule, the cross-platform CWD recipe, and common mistakes.

   Then find the subfolder keys. Claude Code keeps a separate data directory for every subfolder a session ran in, so `OLD_PATH/web` has its own `OLD_KEY-web` beside `OLD_KEY`. List `~/.claude/projects/OLD_KEY-*`; each match that belongs to this project moves to `NEW_KEY` plus the same suffix. A sibling folder can produce a key of the same shape, and the reference's "A subfolder gets its own data directory" entry holds the test that tells the two apart, with `OLD_PATH` as the repo; a candidate it leaves undecided goes to the user as a question, never into the moves unasked.

   Last, check whether the project memory is wired by `link-project-memory.sh`: `~/.claude/projects/OLD_KEY/memory` is then a symlink (`test -L`), and `readlink` shows a target inside `OLD_PATH`. The target is absolute, so after the move it points at a folder that no longer exists and memory stops loading with no error. Subfolder keys carry no such link.

4. **Rename the repo's ports registry claims, where it owns any and has no GitHub origin.** A repo is identified to the ports registry by its GitHub repository name, read from `origin`, which a folder move leaves alone — so where `git -C OLD_PATH remote get-url origin` names a GitHub repository, say the owners need nothing and move on. Only without one is the folder's basename the identity: `ports.py check --repo` then derives it from the main worktree and matches it against each claim's `owner`. Rename such a folder and leave the registry alone, and that check reports every pinned literal in the repo as pinned to some other repo while silently dropping the genuine finding about a port nothing resolves — a repo with a pinned claim then fails its own commit gate on a defect it does not have. Run `python3 ~/.claude/skills/ports/scripts/ports.py list` and read the `owner` column for the old folder name; where nothing carries it, say so and move on. Where something does, edit `owner` in `claude/skills/ports/registry.json` — `amend` does not reach that field, so this is a hand edit — changing only the old name and leaving the other entries of a shared comma-separated `owner` alone. Then run `ports.py check` to prove the document still passes, and `ports.py check --repo NEW_PATH` once the move has happened. That registry lives in the dotfiles repo rather than this one, so report the diff to the session that owns it and leave the commit there.

   **Release the dev-server claims a rename strands, whatever the origin.** The claims are keyed by `ports.py dev-use-case` on the project folder's name, so the next `deploy` allocates fresh ones under the new name and the old pair stays in the registry, owned by the same repo and never used. Before the move, ask for the old slugs with `python3 ~/.claude/skills/ports/scripts/ports.py dev-use-case --from OLD_PATH --role server` and again with `--role tailnet`, rather than spelling them by hand. Where `ports.py list` shows either slug, add `python3 ~/.claude/skills/ports/scripts/ports.py release --use-case <slug>` for each to the commands step 6 hands over; a move that keeps the basename strands nothing. Those release lines edit `claude/skills/ports/registry.json` in the dotfiles repo after this session has exited, so nothing reports that diff to the session owning it: say so in the preview, so the user knows the next commit there will carry the released claims.

5. **Preview and confirm.** Show the user what will happen:
   ```
   Project folder:  OLD_PATH → NEW_PATH
   Claude data:     ~/.claude/projects/OLD_KEY → ~/.claude/projects/NEW_KEY
                    ~/.claude/projects/OLD_KEY-<suffix> → ~/.claude/projects/NEW_KEY-<suffix>   (one line per subfolder key, or: none)
   Memory link:     re-pointed at NEW_PATH/.claude/memory   (or: not linked)
   Ports registry:  <N> claim(s) owned by OLD_NAME → NEW_NAME   (or: none)
   Dev claims:      release <slug>, <slug>; the registry diff is left uncommitted in the dotfiles repo   (or: none)
   ```
   Ask: "Proceed? (y/n)"

6. **Execute on confirmation.** Run these commands (the user must run them outside this session since the working directory is about to move):

   Print the commands for the user to copy and run, chained so each runs only if the one before it succeeded. Drop the second `mv` when `OLD_KEY` does not exist, write one `mv` per subfolder key where the placeholder line stands (none when there are none), and drop the `link-project-memory.sh` line when the memory is not linked:
   ```
   mv "OLD_PATH" "NEW_PATH" && \
   mv "$HOME/.claude/projects/OLD_KEY" "$HOME/.claude/projects/NEW_KEY" && \
   mv "$HOME/.claude/projects/OLD_KEY-SUFFIX" "$HOME/.claude/projects/NEW_KEY-SUFFIX" && \
   bash "$HOME/.claude/scripts/link-project-memory.sh" "NEW_PATH" && \
   curl -sS -w '\nHTTP %{http_code}\n' -X POST http://127.0.0.1:9077/api/project/rename -H 'Content-Type: application/json' -d '{"old_path":"OLD_PATH","new_path":"NEW_PATH"}'
   ```

   The relink must come after the data moves: the script creates `~/.claude/projects/NEW_KEY` when it is missing, and an `mv` onto an existing directory then nests `OLD_KEY` inside it instead of renaming it. On Windows the script refuses unless the shell is elevated, so the user runs the commands from an Administrator shell there.

   The `curl` tells the Claude Code dashboard about the move, so the project's history and custom name follow it to the new name, and synced peers re-file their copy of the history. The dashboard checks that the folder has actually moved, so the call must come after the `mv`. Write both paths in its JSON body with forward slashes (`D:/work/my-app`), since a backslash would have to be escaped there; a path containing a quote character needs escaping for both the shell and JSON. Tell the user:
   - If the dashboard is installed but not running, start it before running the commands: its data stays under the old name until this call is made, and once a session in the new folder has built history there the two can no longer be combined. Skip the call only where the dashboard is not installed; the connection is then refused and nothing else depends on it.
   - `HTTP 409` means nothing was changed, and the `detail` in the reply says what clears it. A Claude Code session still running in the project clears once it exits: run the last command (`curl` or `Invoke-RestMethod`) alone again. A folder that has not moved, an index Claude Code had not finished writing, or another folder of the same name sharing the row (renaming or removing that folder clears it) each say so. A new name that already has history of its own will not clear. A row left behind by a session that exited without telling the dashboard is not a refusal; the call removes it and carries its history over.
   - It must run before a session is opened in the new folder, because such a session holds the new id and the call refuses.
   - A clone of the project on another machine needs this skill run there as well; each dashboard re-files its own data.

   **Important:** Claude Code must NOT be running from the project directory when the move happens. Tell the user to:
   1. Exit this Claude session
   2. Run the printed commands from any other directory
   3. Open a new Claude session from the new location

## Important
- This skill does NOT execute the move itself — it prints the commands. Moving the working directory out from under a running session would break it.
- Read **Platform** from Context. On Windows (`MINGW*`/`MSYS*`/`CYGWIN*`), print both the bash block and a PowerShell variant so the user can run from either shell. The PowerShell variant is one line, using `-ErrorAction Stop` so a failed move ends it before the call: `Move-Item "OLD_PATH" "NEW_PATH" -ErrorAction Stop; Move-Item "$HOME/.claude/projects/OLD_KEY" "$HOME/.claude/projects/NEW_KEY" -ErrorAction Stop; Move-Item "$HOME/.claude/projects/OLD_KEY-SUFFIX" "$HOME/.claude/projects/NEW_KEY-SUFFIX" -ErrorAction Stop; & "$env:ProgramFiles\Git\bin\bash.exe" "$HOME/.claude/scripts/link-project-memory.sh" "NEW_PATH"; if ($LASTEXITCODE) { throw 'memory link not made: re-run link-project-memory.sh from an Administrator shell, then the Invoke-RestMethod alone' }; try { Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9077/api/project/rename -ContentType 'application/json; charset=utf-8' -Body '{"old_path":"OLD_PATH","new_path":"NEW_PATH"}' } catch { if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message } }`. The subfolder and memory-link parts follow the bash block's rules for when to include them. The relink calls the same `link-project-memory.sh` through Git's `bash.exe`, named by full path because a bare `bash` from PowerShell can resolve to WSL's launcher in System32; the script checks elevation before touching the old link, and a native command's failure does not trip `-ErrorAction Stop`, so the `throw` on `$LASTEXITCODE` is what keeps the dashboard call from running after a refusal. The `charset=utf-8` is required: without it Windows PowerShell 5.1 sends the body as Latin-1 and a non-ASCII folder name arrives as `?`. The `try`/`catch` prints a refusal's `detail`, which 5.1 otherwise hides behind a bare `(409) Conflict`, and falls back to the exception text where no reply came at all, such as a dashboard that is not running. Use `Invoke-RestMethod` rather than PowerShell's `curl` alias, which is `Invoke-WebRequest` in Windows PowerShell and does not take curl's flags. On macOS / Linux (`Darwin`/`Linux`), print only the bash block.
- If `~/.claude/projects/OLD_KEY` doesn't exist, skip that step (project may not have Claude data yet). The subfolder keys are found independently, since a subfolder can have sessions when the root has none.
