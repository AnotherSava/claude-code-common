# A git hook killed by a signal passes on Git for Windows

A hook that refuses by printing several lines and then running `exit 1` can be killed partway through its
message by SIGPIPE, when whoever runs git stops reading early — `git commit 2>&1 | head -1`, `grep -m1`, any
tool that truncates output. On macOS and Linux git reports that death as status 141 and treats it as failure.
Git for Windows treats it as success and carries on: the commit is made, or the push is sent, while the one line
that got through says the hook refused.

Measured 2026-09-29 on Git for Windows 2.39.1. A pre-commit hook refusing a plaintext secret let 3 of 3 commits
through behind `| head -1`. A pre-push hook refusing unsigned commits let the push through in 3 of 3 runs of a
case with two unsigned commits, so two `REJECTED` lines and a summary to write after the pipe closed.

## Why

An MSYS bash killed by a signal exits with the Windows code `signal << 8`: `bash -c 'kill -PIPE $$'` returns
3328 (0xD00), `kill -TERM` 0xF00. Git keeps only the low byte of a child's exit code, which is 0.

## The fix

Put `trap '' PIPE` near the top of the hook. With the signal ignored, a write to a closed pipe fails with EPIPE
instead of killing the shell, and the refusal's explicit `exit 1` still runs. Under `set -e` the failed write
ends the script itself with a non-zero status, which blocks the operation as well.

Only the shell and its shell children keep the ignored disposition. Every git program resets SIGPIPE to the
default at startup (`restore_sigpipe_to_default()` in `common-main.c`), so a `git cat-file | head` inside the
hook still dies of it. That is harmless as long as the child's status reaches the hook's own — a child that dies
on the pipe returns non-zero to a `|| exit`, which the hook passes on.

## Testing it

The window sits between one write and the next, so a message printed by back-to-back builtins rarely loses the
race, and one with a subprocess between its lines loses it nearly every time. Give the refusal something to do
between writes (two offending commits rather than one), pipe the real `git commit` or `git push` through
`head -1`, and assert on the repository — `HEAD`, or the remote ref, did not move — never on the pipeline's
exit status, which is `head`'s.
