#!/usr/bin/env python3
"""Pin the decisions of the PreToolUse guards that read Bash commands.

Each case pipes a real hook payload into the hook script, exactly as Claude Code does, and asserts
the decision it prints: deny, a reminder, or nothing. Both guards find command position through
`claude/hooks/_shell.py`, so a change there moves both, and the cases that only *mention* a guarded
command — a grep for it, a heredoc documenting it, a quoted string — are the ones that pin it.

  secret-print-guard   Refuses the commands that print a secret-bearing config whole, and must let
                       the narrow forms that answer the same question run.
  doppler-guard        Denies `doppler secrets set/delete` without `--silent`, and reminds on any
                       other mention of Doppler.
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys

HOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "hooks")
SKILLS = os.path.join(os.path.dirname(HOOKS), "skills")

SECRET_DENY = [
    "git config --local --list",
    "cd C:/work/x && git config --local --list; echo ---remotes; git remote -v",
    "git -C /repo config -l",
    "git --no-pager config --show-origin --list",
    "git config list --local",
    "FOO=1 git config -l",
    "git config --get-regexp transcrypt",
    "git config --get-regexp .",
    "git config --get-regexp",
    "git config --get transcrypt.password",
    "git config transcrypt.password",
    "git config get transcrypt.password",
    "git config --file .git/config --get transcrypt.password",
    "git config --get http.https://github.com/.extraheader",
    "git config --get-urlmatch http https://github.com",
    "cat .git/config",
    "sed -n '1,40p' .git/config",
    "grep -n hookspath .git/config",
    "grep -e hookspath .git/config",
    "head -5 ../other/.git/config",
    "while read l; do echo \"$l\"; done < .git/config",
    # Command position inside loops, conditionals, subshells, groups and wrappers
    "for d in */; do git -C \"$d\" config --local --list; done",
    "for r in a b; do cat $r/.git/config; done",
    "if [ -d .git ]; then cat .git/config; fi",
    "while read r; do git -C \"$r\" config --local --list; done < repos.txt",
    "! git config -l",
    "ls -d */ | xargs -I{} git -C {} config --local --list",
    "(cd C:/work/x && git config --local --list)",
    "(cd ../x && cat .git/config)",
    "(git config -l)",
    "{ cat .git/config; }",
    "time git config -l",
    "env GIT_PAGER=cat git config -l",
    "command git config -l",
    "git config \\\n  --local --list",
    # What a comment or an escaped quote must not hide
    "# don't worry\ngit config --list",
    "echo it\\'s; git config --list",
    # Other shells, other spellings, other readers
    "ssh host.example 'git -C projects/x config --local --list'",
    "bash -c 'git config --list'",
    "git config --get-regex transcrypt",
    "git config -zl",
    "git config --li",
    "git config --get-regexp 'http.*gitlab'",
    "diff a/.git/config b/.git/config",
    "git diff --no-index a/.git/config b/.git/config",
    "cat \"$(git rev-parse --git-dir)/config\"",
    # Multi-line quoted bodies, and substitutions inside double quotes, which bash still runs
    "ssh host.example '\n  cd projects/x\n  git config --local --list\n'",
    "bash -c '\ngit config --list\n'",
    "git commit -m \"$(cat <<'EOF'\nfix: a 5\\\" screen\nEOF\n)\"\ngit config --list",
    "echo \"pw: $(git config transcrypt.password)\"",
    "echo \"$(git config --local --list)\"",
    "echo \"`git config -l`\"",
    "out=\"$(git config --local --list)\"; echo \"$out\"",
    "for d in */; do echo \"== $d: $(git -C \"$d\" config --local --list)\"; done",
    # More shells and wrappers
    "bash -lc 'git config --list'",
    "sh -ec 'git config --list'",
    "eval \"git config --list\"",
    "time -p git config -l",
    "stdbuf -oL git config -l",
    "wsl -d Ubuntu -- git -C /mnt/c/work/x config --list",
    "wsl -e sh -c 'git config --local --list'",
    # What arithmetic, ANSI-C quoting or a mid-word # must not hide
    "echo $((1<<2))\ngit config --list",
    "printf $'don\\'t\\n'; git config --list",
    "git -C repo#1 config --list",
    # Reads that carry a second operand, other listers, the passphrase itself
    "git config --get transcrypt.password .",
    "git config --get-all http.https://github.com/.extraheader AUTH",
    "git var -l",
    "transcrypt --display",
    "transcrypt -d",
    "git config --get-regexp '\\<password\\>'",
    "git config --get-regexp 'http\\.https://ghe\\.corp\\.local/'",
    # A config file reaching a reader through a loop variable, xargs or git's own git-dir
    "for f in C:/work/*/.git/config; do echo \"== $f\"; cat \"$f\"; done",
    "ls -d */.git/config | xargs cat",
    "for r in C:/work/*/; do cat \"$r.git/config\"; done",
    "cat $(git rev-parse --git-dir)/config",
    "git config -f $(git rev-parse --git-dir)/config -l",
    "cat \"$(git rev-parse --absolute-git-dir)/config\"",
    "cat \"$(git rev-parse --git-path config)\"",
    # Process substitution, scripts on stdin, unquoted heredoc bodies
    "diff <(git -C a config --list) <(git -C b config --list)",
    "while IFS= read -r l; do echo \"$l\"; done < <(git config --local --list)",
    "ssh host.example <<'EOF'\ncd projects/x\ngit config --local --list\nEOF",
    "ssh host.example 'bash -s' <<'EOF'\ngit config --local --list\nEOF",
    "bash <<'EOF'\ngit config --list\nEOF",
    "bash <<< 'git config --list'",
    "cat <<EOF\nremote: $(git remote get-url origin)\nconfig: $(git config --local --list)\nEOF",
    # find -exec, submodule foreach, ssh options after the host
    "find . -maxdepth 2 -name .git -exec git -C {}/.. config --list \\;",
    "find . -path '*/.git/config' -exec cat {} +",
    "git submodule foreach 'git config --local --list'",
    "ssh host.example -p 22 'git config --local --list'",
    # Brace and glob spellings, bare redirections, a rebuilt listing, other secret keys
    "cat .git/{HEAD,config}",
    "cat .git/conf*",
    "echo \"$(< .git/config)\"",
    "for f in */.git/config; do git config -f \"$f\" --list; done",
    "git config --list --name-only | xargs -n1 git config --get",
    "for k in $(git config --list --name-only); do git config --get \"$k\"; done",
    "git config --get transcrypt.work.password",
    "git config get --url=https://github.com http",
    "git -C projects/x var -l",
    "function f { git config --list; }; f",
]
SECRET_ALLOW = [
    "git config --get user.name",
    "git config --list --name-only",
    "git config --local --get-regexp '^(core\\.hookspath|user\\.|commit\\.gpgsign)'",
    "git config transcrypt.password newvalue",
    "git config --unset transcrypt.password",
    "git config --file .gitmodules --get-regexp path",
    "grep -rn \".git/config\" docs/",
    "cat <<'EOF' > notes.md\nNever run git config --list here, or cat .git/config.\nEOF",
    "echo \"git config --list\"",
    "git commit -m \"config: tidy\"",
    "git log --oneline -- .git/config",
    "sed -i 's/x/y/' config/settings.json",
    "ls .git/",
    "grep -rn -e \".git/config\" docs/",
    "rg -n --glob '*.md' '.git/config' docs",
    "git config -f .gitmodules --list",
    "git config --blob HEAD:.gitmodules --list",
    "sed -i 's/a/b/' .git/config",
    "cat template > .git/config",
    "cat <<\\EOF > notes.md\ngit config --list\nEOF",
    "cat <<'END-OF-DOC' > notes.md\ncat .git/config\nEND-OF-DOC",
    "# git config --list is refused here\nls",
    # User-level and system config hold no transcrypt passphrase
    "git config -f ~/.gitconfig --list",
    "git config --global --list",
    # Multi-line messages that describe these commands
    "git commit -S -m \"subject\" -m \"body line one\ngit config --list is refused and --get runs.\"",
    "gh pr create --body \"Summary\ncat .git/config and git config -l are now refused.\"",
    "git commit -m \"$(cat <<'EOF'\nfix: a lone \\\" mark\ngit config --list is refused\nEOF\n)\"",
    # Reads that print no content, and ordinary commands that mention config
    "grep -q '\\[transcrypt\\]' .git/config && echo yes",
    "git log --oneline -- .git/config | head -5",
    "echo $(date)#tag; ls",
    "npm config get registry",
    "docker compose config --services",
    "ssh -F ~/.ssh/config host.example uptime",
    "code .git/config",
    # A listing piped into something that prints none of it, and searches for the text itself
    "git config --list | grep -q lfs && echo yes",
    "git config --local --list | wc -l",
    "grep -rln \".git/config\" docs | xargs grep -n foo",
    "cat <<'EOF'\nconfig: $(git config --local --list)\nEOF",
]
DOPPLER = [
    ("doppler secrets set A=b -p x -c y", "deny"),
    ("doppler secrets set A=b -p x -c y --silent", "remind"),
    ("doppler secrets set A=b && echo done --silent", "deny"),
    ("grep -rn \"doppler secrets set\" docs/", "remind"),
    ("cat <<'EOF'\ndoppler secrets set X=1\nEOF", "remind"),
    ("doppler secrets set --help", "remind"),
    ("FOO=1 doppler secrets delete A -p x -c y", "deny"),
    ("echo 'a; doppler secrets set X=1'", "remind"),
    ("ls -la", "silent"),
    ("for p in a b; do doppler secrets set X=1 -p $p -c prd; done", "deny"),
    ("(doppler secrets set X=1 -p x -c y)", "deny"),
    ("# don't forget --silent\ndoppler secrets set X=1 -p x -c y --silent", "remind"),
    ("git commit -S -m \"subject\" -m \"line one\ndoppler secrets set KEY=value prints every value.\"", "remind"),
    ("git commit -m \"$(cat <<'EOF'\nfix: a lone \\\" mark\ndoppler secrets set X=1 -p a -c b now denied\nEOF\n)\"", "remind"),
    ("doppler secrets set JWT_SECRET=$(openssl rand -hex 32) -p app -c prd --silent", "remind"),
    ("doppler secrets set KEY=abc#123 -p x -c y --silent", "remind"),
    ("doppler secrets set X=\"multi\nline\" -p x -c y --silent", "remind"),
    ("X=a#b doppler secrets set Y=1 -p x -c y", "deny"),
    ("echo $(date)#tag; doppler secrets set X=1", "deny"),
    ("echo \"$(doppler secrets set X=1 -p x -c y)\"", "deny"),
    ("ssh host.example <<'EOF'\ncd app && doppler secrets set API_KEY=abc -p app -c prd\nEOF", "deny"),
    ("function setkey { doppler secrets set \"$1=$2\" -p app -c prd; }; setkey A b", "deny"),
]
# The Read tool on a file path: refused for a repository's config, allowed elsewhere.
READ_CASES = [
    ("C:/work/x/.git/config", "deny"),
    ("C:\\work\\x\\.git\\config", "deny"),
    ("/Users/someone/projects/x/.git/config", "deny"),
    ("C:/work/x/config/settings.json", "silent"),
    ("C:/work/x/.gitconfig.example", "silent"),
]


def decide(hook: str, payload: object) -> tuple[int, str]:
    """Run one hook on one payload. -> (exit code, deny | remind | silent | other)."""
    done = subprocess.run([sys.executable, "-S", os.path.join(HOOKS, hook)], input=json.dumps(payload),
                          capture_output=True, text=True, encoding="utf-8", timeout=30)
    out = done.stdout.strip()
    if not out:
        return done.returncode, "silent"
    decision = json.loads(out).get("hookSpecificOutput", {})
    if decision.get("permissionDecision") == "deny":
        return done.returncode, "deny"
    return done.returncode, "remind" if "additionalContext" in decision else "other"


def main() -> int:
    failures, total = [], 0
    cases = [("secret-print-guard.py", c, "deny") for c in SECRET_DENY]
    cases += [("secret-print-guard.py", c, "silent") for c in SECRET_ALLOW]
    cases += [("doppler-guard.py", c, want) for c, want in DOPPLER]
    for path, want in READ_CASES:
        total += 1
        code, got = decide("secret-print-guard.py", {"tool_name": "Read", "tool_input": {"file_path": path}})
        if (code, got) != (0, want):
            failures.append(f"secret-print-guard.py: Read {path!r} -> exit {code}, {got}; want {want}")
    for hook, command, want in cases:
        total += 1
        code, got = decide(hook, {"tool_name": "Bash", "tool_input": {"command": command}})
        if (code, got) != (0, want):
            failures.append(f"{hook}: {command!r} -> exit {code}, {got}; want {want}")
    for hook in ("secret-print-guard.py", "doppler-guard.py"):
        for payload in ("not a dict", {"tool_name": "Bash", "tool_input": {}}, {"tool_name": "Bash", "tool_input": "x"}):
            total += 1
            if decide(hook, payload) != (0, "silent"):
                failures.append(f"{hook}: {payload!r} was not ignored")
    # A skill's `!` Context command runs when the skill loads, before any hook, so no guard sees it.
    # The /transcrypt skill printed the shared passphrase that way on every load until 2026-09-28.
    for skill in sorted(glob.glob(os.path.join(SKILLS, "*", "SKILL.md"))):
        with open(skill, encoding="utf-8") as handle:
            for command in re.findall(r"!`([^`]+)`", handle.read()):
                total += 1
                code, got = decide("secret-print-guard.py", {"tool_name": "Bash", "tool_input": {"command": command}})
                if got != "silent":
                    failures.append(f"{os.path.relpath(skill, SKILLS)} Context line would be refused: {command!r}")
    for line in failures:
        print("FAIL", line)
    print(f"bash guards: {total - len(failures)} of {total} decisions as pinned")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
