#!/usr/bin/env python3
"""PreToolUse guard: refuse a command or a Read that prints a repository's git config whole.

A value printed into the transcript has left the machine, and the only remedy is rotating it. The
rule against doing that is `memory/feedback_never_dump_secret_bearing_config.md`, and on
2026-09-28 it was broken within the hour of being committed, by `git config --local --list` in a
transcrypt repo: the listing includes `transcrypt.password`, the key every repo on the shared
transcrypt passphrase uses. A memory has to be recognised in the moment, and that command looked
like checking git settings rather than like printing a secret. So the known shapes are refused
here, before they run, each with the form that answers the same question safely:

- `git config -l` / `--list` / `list` over a scope that includes the repository's own config,
  `git var -l`, which lists it too, and a listing rebuilt from `--name-only` names fed back into
  `--get`. `--name-only` listings run, and so do `--global`, `--system`, `--blob` and
  `-f <a committed file>` listings, and a listing piped into `grep -q`/`-c`/`-l` or `wc`.
- `git config --get-regexp` / `--get-urlmatch` / `get --url` whose pattern reaches a secret key,
  and `git config <key>` / `--get` / `--get-all` / `get` on a secret key.
- `transcrypt -d` / `--display`, which prints the passphrase as a ready-to-paste command.
- A reader (`cat`, `sed`, `grep`, `diff`, …) given a repository's config as a file: directly, as a
  `<` redirection, through a loop variable, `xargs` or `find -exec`, or spelled with braces or a
  glob. A search *for* the text `.git/config` is not a read of it, nor is a write or a `grep -q`.
- The Read tool on a repository's config.
- Any of these inside `$( … )`, backticks, process substitution, an unquoted heredoc,
  `ssh host '…'`, `bash -c '…'`, `eval`, a script fed to a shell or ssh on stdin, `find -exec`
  or `git submodule foreach`.

The command each one runs is found by `_shell.commands`, which tokenizes the way bash does.

What it cannot see:
- a script that loads a config and prints part of it — the 2026-09-27 case, a JSON file's
  `notifications` block carrying a bot token — since no command text says which printed values
  are secrets;
- a recursive search from a repository root, such as `grep -rn password .`, which reads
  `.git/config` among everything else without naming it (the Grep tool skips `.git`);
- a relative path from inside the git dir (`cd .git && cat config`), and a script piped into a
  shell (`… | bash`);
- a script fed on a heredoc, such as `bash <<'EOF'` or `ssh host <<'EOF'` wrapping a listing,
  unless the command line itself also matches a filter. The `if` patterns see neither a heredoc
  body nor its `<<`: measured 2026-09-29, `Bash(*<<*)` never fired on one. So the heredoc handling
  below runs only when some other part of the command started the guard;
- bash constructs `_shell` reads as plain words — arithmetic contents, `case` patterns inside a
  substitution, `${ … }` operators, escaped nested backticks;
- a skill's `!` Context command, which runs when the skill loads, before any hook; the commit gate
  checks those instead (`claude/tests/bash-guards.py`).
For those the memory is the only guard.

Registered in settings.json on `^Bash$` behind `if` filters for `*config*`, `*transcrypt*`,
`*var -l*` and `*var --list*`, and on `^Read$` behind `Read(//**/.git/config)`; a call that
matches none starts no process. The filters fail open on commands the harness cannot decompose
and never see a heredoc body, so the command text is re-read here rather than trusted.
"""

from __future__ import annotations

import fnmatch
import json
import re
import sys

from _shell import command_argv, commands, nested_scripts, tool_name

# Keys whose value is itself a credential. Matched case-insensitively, as git folds section and key
# names; `http.<url>.extraheader` is where CI and credential helpers put bearer tokens, and a
# transcrypt context keeps its own passphrase at `transcrypt.<context>.password`.
SECRET_KEYS = (re.compile(r"^transcrypt\.(?:[^.]+\.)?password$"), re.compile(r"^http\.(?:.*\.)?extraheader$"))
SECRET_EXAMPLES = ("transcrypt.password", "transcrypt.work.password", "http.extraheader",
                   "http.https://example.com/.extraheader")

GIT_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}
CONFIG_OPTIONS_WITH_VALUE = {"-f", "--file", "--blob", "--type", "--default", "--comment", "--value", "--url"}
CONFIG_LONG_OPTIONS = (
    "--list", "--get", "--get-all", "--get-regexp", "--get-urlmatch", "--name-only", "--null", "--show-origin",
    "--show-scope", "--file", "--blob", "--global", "--system", "--local", "--worktree", "--includes",
    "--no-includes", "--type", "--default", "--unset", "--unset-all", "--add", "--replace-all", "--regexp", "--all",
    "--value", "--comment", "--edit", "--rename-section", "--remove-section", "--fixed-value", "--bool", "--int",
    "--path", "--expiry-date", "--get-color", "--get-colorbool", "--url")
READ_ACTIONS = {"--get", "--get-all", "--get-regexp", "--get-urlmatch"}

READERS = {"cat", "head", "tail", "less", "more", "bat", "sed", "awk", "gawk", "grep", "egrep", "fgrep", "rg",
           "nl", "od", "xxd", "hexdump", "strings", "cut", "sort", "uniq", "tac", "type", "diff", "sdiff",
           "comm", "paste"}
# Options that take the next word as a value, per reader, and the ones among them whose value is
# the search pattern or script — never a file, however it reads.
READER_OPTIONS = {
    "grep": ({"-e", "--regexp", "-f", "--file", "-A", "-B", "-C", "-m", "--max-count", "-d", "-D",
              "--include", "--exclude", "--exclude-dir", "--label"}, {"-e", "--regexp", "-f", "--file"}),
    "rg": ({"-e", "--regexp", "-f", "--file", "-A", "-B", "-C", "-m", "--max-count", "-g", "--glob", "-t",
            "--type", "-T", "--type-not", "-j", "--threads"}, {"-e", "--regexp", "-f", "--file"}),
    "sed": ({"-e", "--expression", "-f", "--file", "-l", "--line-length"}, {"-e", "--expression", "-f", "--file"}),
    "awk": ({"-f", "--file", "-v", "--assign", "-F", "--field-separator"}, {"-f", "--file"}),
    "head": ({"-n", "-c", "--lines", "--bytes"}, set()),
    "tail": ({"-n", "-c", "--lines", "--bytes"}, set()),
    "cut": ({"-d", "-f", "-c", "-b", "--delimiter", "--fields"}, set()),
    "sort": ({"-k", "-t", "-o", "-S", "-T", "--key", "--field-separator", "--output"}, set()),
    "diff": ({"-U", "-C", "-L", "--label", "-x", "-X", "-I"}, set()),
    "od": ({"-N", "-j", "-A", "-t", "-w"}, set()),
    "xxd": ({"-c", "-g", "-l", "-s", "-o"}, set()),
}
for alias, base in (("egrep", "grep"), ("fgrep", "grep"), ("gawk", "awk"), ("sdiff", "diff")):
    READER_OPTIONS[alias] = READER_OPTIONS[base]
PATTERN_FIRST = {"grep", "egrep", "fgrep", "rg", "sed", "awk", "gawk"}
GREPS = {"grep", "egrep", "fgrep", "rg"}
QUIET_GREP = {"-q", "--quiet", "--silent", "-c", "--count", "-l", "--files-with-matches", "-L", "--files-without-match"}
QUIET_BUNDLE = re.compile(r"-[a-zA-Z]*[qclL][a-zA-Z]*")

# A path naming a repository's config: `.git/config` after a directory, a glob or a variable, or the
# git dir asked of git itself.
REPO_CONFIG = re.compile(
    r"(?:(?:^|[/\\*]|\$\w+|\$\{\w+\}|\})\.git[/\\]+config"
    r"|(?:--git-dir|--git-common-dir|--absolute-git-dir)\)[/\\]+config"
    r"|--git-path\s+config\)"
    r"|\$\{?GIT_DIR\}?[/\\]+config)$")
GIT_DIR_GLOB = re.compile(r"(?:^|[/\\*])\.git[/\\]+([^/\\]*[*?\[][^/\\]*)$")
BRACES = re.compile(r"\{([^{}]*,[^{}]*)\}")

SAFE_FORM = ("Ask for the keys you need with `git config --get <key>`, or list names only with "
             "`git config --list --name-only`.")

# A key whose VALUE is the secret has no permitted read form, so SAFE_FORM would name the very
# command being refused. Say what is available instead: presence, and answers derived without it.
NO_READ_FORM = ("A key whose value is itself a secret has no safe read form — `--get` on it is this same "
                "refusal. Confirm it is set with `git config --name-only --get-regexp '<prefix>'`, and "
                "derive any other answer without materialising the value.")


def is_secret(key: str) -> bool:
    return any(pattern.match(key.lower()) for pattern in SECRET_KEYS)


def expansions(word: str) -> list[str]:
    """The word with each `{a,b}` brace alternative spelled out, as bash expands it."""
    match = BRACES.search(word)
    if not match:
        return [word]
    return [w for part in match.group(1).split(",") for w in expansions(word[:match.start()] + part + word[match.end():])]


def is_repo_config(word: str) -> bool:
    for candidate in expansions(word):
        if REPO_CONFIG.search(candidate):
            return True
        glob = GIT_DIR_GLOB.search(candidate)
        if glob and fnmatch.fnmatchcase("config", glob.group(1)):
            return True
    return False


def git_subcommand(argv: list[str]) -> tuple[str, list[str]] | None:
    """(subcommand, its arguments) for a `git` invocation, past git's own options; None otherwise."""
    if not argv or tool_name(argv[0]) != "git":
        return None
    i = 1
    while i < len(argv) and argv[i].startswith("-"):
        i += 2 if argv[i] in GIT_OPTIONS_WITH_VALUE else 1
    return (argv[i], argv[i + 1:]) if i < len(argv) else None


def normalise_option(arg: str) -> list[str]:
    """The option(s) git reads this word as: a bundle `-zl` is `-z -l`, a unique prefix its full name."""
    if re.fullmatch(r"-[A-Za-z]{2,}", arg):
        return [f"-{letter}" for letter in arg[1:]]
    if arg.startswith("--"):
        key = arg.split("=", 1)[0]
        if key not in CONFIG_LONG_OPTIONS:
            matches = [option for option in CONFIG_LONG_OPTIONS if option.startswith(key)]
            if len(matches) == 1:
                return matches
        return [key]
    return [arg]


def split_config_args(args: list[str]) -> tuple[list[str], list[str], dict[str, str]]:
    """(options, operands, option values) of a `git config` call."""
    options, operands, values = [], [], {}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("-") and arg != "-":
            for option in normalise_option(arg):
                options.append(option)
                if arg.startswith("--") and "=" in arg:
                    values[option] = arg.split("=", 1)[1]
                elif option in CONFIG_OPTIONS_WITH_VALUE and i + 1 < len(args):
                    values[option] = args[i + 1]
                    i += 1
        else:
            operands.append(arg)
        i += 1
    return options, operands, values


def regexp_reaches_secret(pattern: str) -> bool:
    """Would `git config --get-regexp <pattern>` print a secret key? Unreadable counts as yes.

    Any pattern naming `http` counts, since an extraheader sits under whichever URL it was set for
    and no sample of hosts covers them all.
    """
    if "[[:" in pattern or re.search(r"http", pattern, re.IGNORECASE):
        return True
    try:
        compiled = re.compile(pattern.replace(r"\<", r"\b").replace(r"\>", r"\b"), re.IGNORECASE)
    except re.error:
        return True
    return any(compiled.search(example) for example in SECRET_EXAMPLES)


def config_refusal(args: list[str], names_config: bool, names_listed: bool, via_xargs: bool) -> str | None:
    """Why this `git config` invocation prints a secret, or None when it does not."""
    options, operands, values = split_config_args(args)
    if "--name-only" in options:
        return None
    source = values.get("--file") or values.get("-f")
    source_in_repo = source and (is_repo_config(source) or (names_config and ("$" in source or "{}" in source)))
    if "--blob" in values or "--global" in options or "--system" in options or (source and not source_in_repo):
        return None  # outside the repository's own config, where transcrypt keeps its passphrase
    subcommand = operands[0] if operands and operands[0] in ("list", "get") else None
    if subcommand:
        operands = operands[1:]
    if subcommand == "list" or "-l" in options or "--list" in options:
        return "it lists every value in the repository's git config, where a transcrypt repo keeps its passphrase as `transcrypt.password`"
    url_lookup = "--get-urlmatch" in options or (subcommand == "get" and "--url" in values)
    if "--get-regexp" in options or url_lookup or (subcommand == "get" and "--regexp" in options):
        if not operands or regexp_reaches_secret(operands[0]):
            return "its pattern reaches a key whose value is a secret, such as `transcrypt.password`"
        return None
    reading = subcommand == "get" or any(o in READ_ACTIONS for o in options)
    writing = not reading and (len(operands) >= 2 or any(o in options for o in ("--unset", "--unset-all", "--add", "--replace-all")))
    if writing:
        return None
    if operands and is_secret(operands[0]):
        return f"it prints the value of `{operands[0]}`, which is a secret"
    key_from_elsewhere = (not operands and via_xargs) or (operands and "$" in operands[0])
    if reading and names_listed and key_from_elsewhere:
        return "it reads back every key a `--name-only` listing names, which rebuilds the whole listing"
    return None


def prints_content(argv: list[str]) -> bool:
    """Does this reader print what it reads? An in-place edit or a quiet grep does not."""
    tool, rest = tool_name(argv[0]), argv[1:]
    if tool == "sed" and any(w in ("-i", "--in-place") or w.startswith(("-i", "--in-place=")) for w in rest):
        return False
    return not (tool in GREPS and any(w in QUIET_GREP or QUIET_BUNDLE.fullmatch(w) for w in rest))


def reader_operands(argv: list[str]) -> list[str] | None:
    """The files a reader reads, its search pattern or script excluded, or None for a non-reader."""
    tool = tool_name(argv[0])
    rest = argv[1:]
    if tool not in READERS:
        return None
    takes_value, pattern_options = READER_OPTIONS.get(tool, (set(), set()))
    operands, pattern_given, i = [], False, 0
    while i < len(rest):
        word = rest[i]
        if word.split("=", 1)[0] in pattern_options:
            pattern_given = True
        if word in takes_value:
            i += 2
            continue
        if not word.startswith("-") or word == "-":
            operands.append(word)
        i += 1
    if tool in PATTERN_FIRST and not pattern_given:
        operands = operands[1:]
    return operands


def quiet_consumer(argv: list[str]) -> bool:
    """Does this command take piped input and print none of its content?"""
    if not argv:
        return False
    tool = tool_name(argv[0])
    return tool == "wc" or (tool in GREPS and any(w in QUIET_GREP or QUIET_BUNDLE.fullmatch(w) for w in argv[1:]))


def refusal(command: str, depth: int = 0, outer_names_config: bool = False) -> str | None:
    """Why this command would print a repository's git config, or None when it would not.

    `outer_names_config` carries into a nested script (a `find -exec` command, say) that the
    command line around it already named a repository's config.
    """
    found = commands(command)
    argvs = [command_argv(c.argv) for c in found]
    # Which files the command line names: a reader's file operands, or any word of any other command
    # (a `for` list, a `find -path`), but never a pattern a reader searches for.
    named = []
    for cmd, argv in zip(found, argvs):
        operands = reader_operands(argv) if argv else None
        named += operands if operands is not None else argv
        named += [target for _, target in cmd.redirects]
    names_config = outer_names_config or any(is_repo_config(w) for w in named)
    names_listed = any(w == "--name-only" for argv in argvs for w in argv)
    for index, (cmd, argv) in enumerate(zip(found, argvs)):
        if any(op in ("<", "<>", "<&") and is_repo_config(target) for op, target in cmd.redirects):
            return f"`{' '.join(cmd.argv) or '<'}` is refused because it reads a repository's git config into a command. {SAFE_FORM}"
        if not argv:
            continue
        shown = " ".join(argv)
        via_xargs = any(tool_name(w) == "xargs" for w in cmd.argv[:len(cmd.argv) - len(argv)])
        sub = git_subcommand(argv)
        if sub and sub[0] == "config":
            why = config_refusal(sub[1], names_config, names_listed, via_xargs)
            piped_quietly = cmd.sep == "|" and index + 1 < len(found) and quiet_consumer(argvs[index + 1])
            if why and not (piped_quietly and "lists every value" in why):
                tail = NO_READ_FORM if "which is a secret" in why else SAFE_FORM
                return f"`{shown}` is refused because {why}. {tail}"
        if sub and sub[0] == "var" and any(a in ("-l", "--list") for a in sub[1]):
            return f"`{shown}` is refused because `git var -l` lists every git config value too. {SAFE_FORM}"
        if tool_name(argv[0]) == "transcrypt" and any(a == "--display" or re.fullmatch(r"-[a-zA-Z]*d[a-zA-Z]*", a) for a in argv[1:]):
            return (f"`{shown}` is refused because it prints the transcrypt passphrase. To see whether a repo "
                    f"is configured, run `git config --name-only --get-regexp '^transcrypt\\.'`.")
        if sub and sub[0] == "diff" and "--no-index" in sub[1] and any(is_repo_config(w) for w in sub[1]):
            return f"`{shown}` is refused because it prints a repository's git config. {SAFE_FORM}"
        operands = reader_operands(argv)
        if operands is not None and prints_content(argv):
            indirect = names_config and (via_xargs or any("$" in w or "{}" in w for w in operands))
            if any(is_repo_config(w) for w in operands) or indirect:
                return (f"`{shown}` is refused because it prints a repository's git config, where a transcrypt "
                        f"repo keeps its passphrase. {SAFE_FORM}")
        if depth < 3:
            for script in nested_scripts(argv, cmd.stdin):
                inner = refusal(script, depth + 1, names_config)
                if inner:
                    return inner
    return None


def read_refusal(path: str) -> str | None:
    if is_repo_config(path.replace("\\", "/")):
        return ("Reading a repository's `.git/config` shows everything in it, and a transcrypt repo keeps its "
                "passphrase there as `transcrypt.password`. " + SAFE_FORM)
    return None


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # never break a tool call on a parse hiccup
    tool_input = data.get("tool_input") if isinstance(data, dict) else None
    if not isinstance(tool_input, dict):
        return 0
    try:
        if data.get("tool_name") == "Read":
            path = tool_input.get("file_path")
            reason = read_refusal(path) if isinstance(path, str) else None
        else:
            command = tool_input.get("command")
            reason = refusal(command) if isinstance(command, str) else None
    except Exception as exc:
        # Let the call through, since a guard that cannot read it must not take the tool down, but
        # say so: a silent pass here would read as a call found safe.
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext":
                          f"secret-print-guard could not read this call ({type(exc).__name__}: {exc}), so it was not checked."}}))
        return 0
    if reason:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
