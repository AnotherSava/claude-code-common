# Windows will not delete a directory some process is standing in

Every process holds an open handle on its current directory, and Windows opens it without
`FILE_SHARE_DELETE`, so removing that directory — or a tree containing it — fails for as long as any
process has its cwd there. macOS and Linux unlink it regardless and leave the process in a deleted
directory. So code that tears down a temp tree from inside it passes every POSIX test and fails only
on Windows: measured 2026-10-14, `git worktree remove --force <dir>` exited 255 when the script
calling it had been started with `cwd=<dir>`, even though git itself ran with `cwd` set elsewhere.

Two holders, and only one is fixable from the code:

- **The process doing the removal.** Passing `cwd=` to the child is not enough; the parent's own cwd
  still pins the directory. `os.chdir()` out before removing.
- **Whoever launched it.** A shell that ran `cd <dir> && python remove.py <dir>` holds the directory
  for the length of the command, and nothing the script does can release it. The caller has to `cd`
  out first, so say so wherever the command is documented.
