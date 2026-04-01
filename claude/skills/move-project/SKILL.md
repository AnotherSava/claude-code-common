# Move/Rename Project

Move or rename the current project folder while preserving all associated Claude Code data (session logs, memory, subagent history).

## Process

1. **Ask for the new location.** If the user didn't provide one as an argument, ask:
   > Where should I move this project? Provide a new folder path (relative or absolute) or just a new name (keeps the same parent directory).

2. **Resolve paths.** Determine:
   - `OLD_PATH`: the current working directory (absolute)
   - `NEW_PATH`: the target — if the user gave just a name, resolve it relative to the parent of `OLD_PATH`
   - Validate that `NEW_PATH` does not already exist

3. **Compute Claude data directory names.** Claude stores project data in `~/.claude/projects/<key>/` where `<key>` is the absolute path with every `:`, `\`, and `/` replaced by a single `-`.
   - `D:` has both `:` and `\` after it — each becomes `-`, so `D:\` → `D--` (two consecutive single replacements, not a special double-dash separator).
   - Examples:
     - `D:\projects\my-app` → `D--projects-my-app`
     - `D:\projects\games\achievement-overlay` → `D--projects-games-achievement-overlay`
   - **Common mistake:** do NOT replace path separators with `--` (double dash). Each `:`, `\`, `/` becomes exactly one `-`.

   Compute `OLD_KEY` and `NEW_KEY` from the old and new paths.

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
- On Windows, print both bash (`mv`) and PowerShell (`Move-Item`) variants so the user can run from either shell.
- If `~/.claude/projects/OLD_KEY` doesn't exist, skip that step (project may not have Claude data yet).
