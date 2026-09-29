---
created: 2026-09-29 03:28:33
---

# Find which command makes grep.exe crash with a stackdump in the dotfiles repo

A grep.exe.stackdump appeared in the dotfiles repo root three times on 2026-09-28/29, and each was deleted unread. Each time it followed a run of `bash .claude/commit-checks.sh >tmp/gate.log 2>&1` and then a pipe like `grep -iE 'fail|error' tmp/gate.log | grep -v ' 0 failed' | head -5`, in Git Bash on Windows. The same pipe with head -3 once produced no dump, so it is not reproducible on demand yet. Next step: when one appears, read it before deleting it (it names the faulting module and the stack), note the exact preceding command, then try that command in a loop to reproduce. Suspects: grep taking SIGPIPE when head exits early, or a grep call inside one of the gate's suites.

Fourth occurrence, 2026-09-29 during /wrap-up, with no commit gate involved: `grep -n -i -e 'def ' -e 'doppler' claude/hooks/doppler-guard.py | head -40; grep -rn 'doppler-guard' README.md claude/skills/hooks/SKILL.md | cut -c1-200 | head`. The first grep printed nothing although the file has many matches, so that grep is the one that died, before writing any output. The dump held a 7-frame stack of addresses in the msys runtime (0x0021xxxxxxx) and one at 0x0010042A1E5, with no exception line. So the gate is ruled out as the trigger. `-i` together with several `-e` patterns on a small file is the cheapest thing to try first.

Fifth occurrence, minutes later: `grep -n -i -e 'heredoc' -e 'cannot see' -e 'limits' claude/hooks/secret-print-guard.py | head`, again with no output although the second pattern matches. Both of today's non-gate crashes combine `-n -i` with three `-e` patterns, piped into `head`.

Sixth, during /commit's reflect: `grep -n -i -e 'backfill' -e 'push --all' -e 'before the fix' -e 'fresh clone' <learning>.md | head` died the same way. That is three in a row for `-n -i` with several `-e` patterns into `head`, so it now looks reproducible on demand.
