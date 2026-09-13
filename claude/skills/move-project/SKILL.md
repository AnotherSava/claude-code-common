---
name: move-project
description: >-
  Move or rename the current project folder without losing the Claude Code data keyed to its old
  path — session logs, memory and subagent history — by working out the new data directory name
  and printing the two moves for the user to run from outside the session.
  TRIGGER when: the user wants to move, rename or relocate the folder of the project they are
  working in, or asks what happens to their session history and memory if they do.
  DO NOT TRIGGER when: renaming the GitHub repository without moving the local folder, moving
  files around inside the project, or creating a new project (that is `github-create`).
allowed-tools: Read, Glob, Bash(pwd:*), Bash(git rev-parse:*), Bash(test -e:*), Bash(test -d:*), Bash(uname:*)
---

# Move/Rename Project

Move or rename the current project folder while preserving all associated Claude Code data (session logs, memory, subagent history).

## Context
- Current project path: !`pwd`
- Platform: !`uname -s`

## Process

1. **Ask for the new location.** If the user didn't provide one as an argument, ask:
   > Where should I move this project? Provide a new folder path (relative or absolute) or just a new name (keeps the same parent directory).

2. **Resolve paths.** Determine:
   - `OLD_PATH`: **Current project path** from Context
   - `NEW_PATH`: the target — if the user gave just a name, resolve it relative to the parent of `OLD_PATH`
   - Validate that `NEW_PATH` does not already exist (`test -e "NEW_PATH"`)

3. **Compute Claude data directory names.** Apply the path-mangling rule documented in `~/.claude/skills/skill/references/claude-project-memory-paths.md` to both `OLD_PATH` and `NEW_PATH` to derive `OLD_KEY` and `NEW_KEY`. That file is the canonical reference for the mangling rule, the cross-platform CWD recipe, and common mistakes.

4. **Preview and confirm.** Show the user what will happen:
   ```
   Project folder:  OLD_PATH → NEW_PATH
   Claude data:     ~/.claude/projects/OLD_KEY → ~/.claude/projects/NEW_KEY
   ```
   Ask: "Proceed? (y/n)"

5. **Execute on confirmation.** Run these commands (the user must run them outside this session since the working directory is about to move):

   Print the commands for the user to copy and run:
   ```
   mv "OLD_PATH" "NEW_PATH"
   mv "$HOME/.claude/projects/OLD_KEY" "$HOME/.claude/projects/NEW_KEY"
   ```

   **Important:** Claude Code must NOT be running from the project directory when the move happens. Tell the user to:
   1. Exit this Claude session
   2. Run the printed commands from any other directory
   3. Open a new Claude session from the new location

## Important
- This skill does NOT execute the move itself — it prints the commands. Moving the working directory out from under a running session would break it.
- Read **Platform** from Context. On Windows (`MINGW*`/`MSYS*`/`CYGWIN*`), print both bash (`mv`) and PowerShell (`Move-Item`) variants so the user can run from either shell. On macOS / Linux (`Darwin`/`Linux`), print only the bash `mv` form.
- If `~/.claude/projects/OLD_KEY` doesn't exist, skip that step (project may not have Claude data yet).
