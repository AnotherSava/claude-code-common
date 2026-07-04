---
name: feedback_heredoc_python_stdin
description: Can't pipe data into `python <<'EOF'` — the heredoc redirect replaces the pipe on stdin; pass via a temp file + argv instead
metadata:
  type: feedback
---

`cmd | python <<'EOF' … EOF` does **not** deliver `cmd`'s output to `sys.stdin`. The `<<'EOF'` redirect overrides the pipe, and the interpreter consumes the heredoc as its *program* — so `sys.stdin.read()` returns `''` and the piped data is silently lost (empty output, wasted round-trips).

**Why:** redirections apply after the pipe, so the heredoc wins on stdin; `python` invoked with no script argument reads its *program* from stdin (the heredoc).

**How to apply:** write the data to a temp file, then `cmd > f; python - f <<'EOF'` and read `sys.argv[1]` inside the script. On Windows also force UTF-8 (`sys.stdout.reconfigure(encoding="utf-8")`) before printing box-drawing / non-ASCII or the cp125x console codec raises `UnicodeEncodeError`. Complements the global "use a heredoc, not `python -c`" rule.
