"""Reading a Bash command the way the shell will, for the PreToolUse guards that inspect one.

A guard that matches text anywhere in a command blocks the commands that only mention the thing it
guards: a `grep` for the verb, a commit message describing it, a heredoc writing the docs. A guard
that looks only at the first word of each line misses the same command inside a loop, a subshell or
a `$( … )`. So the guards judge the simple commands the shell will actually run, and `commands`
finds them with a tokenizer that follows bash's own rules rather than approximating them with
patterns — an approximation fails on every nesting it did not anticipate, which is how two review
rounds of a mask-and-split version kept finding new ways through:

- Quoting decides what a word is: single quotes are literal, double quotes keep `$( … )`,
  backticks and `$(( … ))` live, `$' … '` honours backslash escapes, and a backslash outside quotes
  escapes one character or, before a newline, continues the line.
- A `#` starts a comment only at the start of a word.
- A heredoc's body is text, however it reads, and starts at the next line the shell would read —
  also inside a `$( … )`, where each substitution tokenizes with state of its own.
- Every `$( … )` and backtick body is a list of commands in its own right, reported alongside the
  command that contains it; that command keeps the substitution's raw text in its word, so a path
  such as `$(git rev-parse --git-dir)/config` can still be recognised.

What the tokenizer does not model — `case` patterns, `(( … ))` contents, aliases, functions — reads
as ordinary words, which can only produce a command nobody runs, never hide one that is.
"""

from __future__ import annotations

import re
from typing import NamedTuple


class Command(NamedTuple):
    """One simple command: its words with quotes removed, its redirections, what it reads as a
    script on stdin, and the operator that ended it."""

    argv: list[str]
    redirects: list[tuple[str, str]]  # (operator, target), e.g. ("<", ".git/config"), ("<<", "EOF")
    stdin: list[str]  # heredoc bodies and here-strings, which a shell or ssh given no -c would run
    sep: str  # "|" when its output feeds the next command at the same level


_OPERATOR_CHARS = set(";&|()\n")
_TWO_CHAR_OPERATORS = ("&&", "||", ";;", "|&")
_WORD_ENDS = set(" \t\r;&|()<>\n")
_REDIRECT_OPERATORS = ("<<<", "<<-", "&>>", "<<", "<>", "<&", ">>", ">|", ">&", "&>", "<", ">")

RESERVED = {"do", "then", "else", "elif", "if", "while", "until", "!", "{", "}", "time", "coproc"}
# Wrappers that run the words after them as a command, with their options that take a value.
WRAPPERS = {
    "command": set(), "exec": set(), "nohup": set(), "builtin": set(), "stdbuf": set(),
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"},
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U"},
    "xargs": {"-I", "-i", "-n", "-P", "-L", "-l", "-d", "-E", "-e", "-s", "-a", "--arg-file", "--delimiter"},
    "nice": {"-n", "--adjustment"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "wsl": {"-d", "--distribution", "-u", "--user", "--cd"},
}
_TAKES_POSITIONAL = {"timeout"}  # `timeout 20 cmd`: the duration comes before the command
_WRAPPER_MARKERS = {"wsl": {"-e", "--exec", "--"}}  # what ends the wrapper's own options


class _Tokenizer:
    def __init__(self, text: str) -> None:
        self.text, self.i, self.found = text, 0, []

    def peek(self, offset: int = 0) -> str:
        j = self.i + offset
        return self.text[j] if j < len(self.text) else ""

    def parse(self, end: str | None) -> None:
        """Tokenize until `end` (`)` or a backtick) closes this level, or the text runs out."""
        words: list[str] = []
        redirects: list[tuple[str, str]] = []
        stdin: list[str] = []
        heredocs: list[tuple[str, bool, bool, list[str]]] = []  # (delimiter, strip tabs, quoted, owner's stdin)
        word: list[str] = []
        started, pending, depth = False, None, 0

        def finish_word() -> None:
            nonlocal word, started, pending
            if started:
                value = "".join(word)
                if pending is not None:
                    redirects.append((pending, value))
                    if pending == "<<<":
                        stdin.append(value)
                    pending = None
                else:
                    words.append(value)
            word, started = [], False

        def finish_command(sep: str = "") -> None:
            nonlocal stdin, pending
            finish_word()
            if words or redirects:
                # `stdin` is handed over by reference: a heredoc body is read after its line ends,
                # by which time the command that owns it has already been recorded.
                self.found.append(Command(list(words), list(redirects), stdin, sep))
            words.clear()
            redirects.clear()
            stdin, pending = [], None

        text = self.text
        while self.i < len(text):
            c = text[self.i]
            if end == "`" and c == "`":
                self.i += 1
                finish_command()
                return
            if end == ")" and c == ")" and depth == 0:
                self.i += 1
                finish_command()
                return
            if c in " \t\r":
                finish_word()
                self.i += 1
            elif c == "\n":
                finish_command("\n")
                self.i += 1
                for delimiter, strip_tabs, quoted, sink in heredocs:
                    sink.append(self.read_heredoc(delimiter, strip_tabs, quoted))
                heredocs = []
            elif c == "#" and not started:
                while self.i < len(text) and text[self.i] != "\n":
                    self.i += 1
            elif c == "\\":
                if self.peek(1) == "\n":
                    self.i += 2
                elif self.peek(1) == "\r" and self.peek(2) == "\n":
                    self.i += 3
                else:
                    word.append(self.peek(1))
                    started, self.i = True, self.i + 2
            elif c == "'":
                word.append(self.single_quoted())
                started = True
            elif c == '"':
                word.append(self.double_quoted())
                started = True
            elif c == "$" and self.peek(1) == "'":
                word.append(self.ansi_c_quoted())
                started = True
            elif c == "$" and self.peek(1) == "(":
                word.append(self.substitution())
                started = True
            elif c == "`":
                word.append(self.backtick())
                started = True
            elif c == "(" and not started and self.peek(1) == "(":
                word.append(self.arithmetic())  # an arithmetic command, `(( … ))`
                started = True
            elif c == "&" and self.peek(1) == ">":
                finish_word()
                pending = self.redirect_operator()
            elif c in "<>" and self.peek(1) == "(":
                start = self.i  # process substitution, `<( … )` or `>( … )`: commands of its own
                self.i += 2
                self.parse(")")
                word.append(self.text[start:self.i])
                started = True
            elif c in "<>":
                if started and "".join(word).isdigit():
                    word, started = [], False  # a file-descriptor prefix, as in `2>`
                finish_word()
                operator = self.redirect_operator()
                if operator in ("<<", "<<-"):
                    delimiter, quoted = self.heredoc_delimiter()
                    heredocs.append((delimiter, operator == "<<-", quoted, stdin))
                    redirects.append((operator, delimiter))
                else:
                    pending = operator
            elif c in _OPERATOR_CHARS:
                if c == "(" and end == ")":
                    depth += 1
                elif c == ")" and depth > 0:
                    depth -= 1
                operator = next((op for op in _TWO_CHAR_OPERATORS if text.startswith(op, self.i)), c)
                finish_command(operator)
                self.i += len(operator)
            else:
                word.append(c)
                started, self.i = True, self.i + 1
        finish_command()

    def redirect_operator(self) -> str:
        for operator in _REDIRECT_OPERATORS:
            if self.text.startswith(operator, self.i):
                self.i += len(operator)
                return operator
        self.i += 1
        return self.text[self.i - 1]

    def heredoc_delimiter(self) -> tuple[str, bool]:
        """The delimiter word after `<<` with its quoting removed, and whether any of it was quoted.

        Quoting any part of the delimiter makes the body literal; otherwise bash expands `$( … )`
        and backticks in it, which run as commands.
        """
        while self.peek() in (" ", "\t"):
            self.i += 1
        out, quoted = [], False
        while self.i < len(self.text) and self.text[self.i] not in _WORD_ENDS:
            c = self.text[self.i]
            if c == "\\":
                out.append(self.peek(1))
                self.i, quoted = self.i + 2, True
            elif c in "'\"":
                closing = self.text.find(c, self.i + 1)
                closing = len(self.text) if closing == -1 else closing
                out.append(self.text[self.i + 1:closing])
                self.i, quoted = closing + 1, True
            else:
                out.append(c)
                self.i += 1
        return "".join(out), quoted

    def read_heredoc(self, delimiter: str, strip_tabs: bool, quoted: bool) -> str:
        """Consume a heredoc body up to its delimiter line and return it.

        The body is text either way. With an unquoted delimiter, its `$( … )` and backtick spans
        still run, so each is tokenized as commands of its own.
        """
        text, lines = self.text, []
        while self.i < len(text):
            end = text.find("\n", self.i)
            end = len(text) if end == -1 else end
            line = text[self.i:end].rstrip("\r")
            self.i = end + 1
            if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                break
            lines.append(line)
        body = "\n".join(lines)
        if not quoted:
            self.found.extend(_substitutions_in(body))
        return body

    def single_quoted(self) -> str:
        closing = self.text.find("'", self.i + 1)
        closing = len(self.text) if closing == -1 else closing
        value = self.text[self.i + 1:closing]
        self.i = closing + 1
        return value

    def ansi_c_quoted(self) -> str:
        self.i += 2
        out = []
        while self.i < len(self.text) and self.text[self.i] != "'":
            if self.text[self.i] == "\\":
                out.append(self.text[self.i:self.i + 2])
                self.i += 2
            else:
                out.append(self.text[self.i])
                self.i += 1
        self.i += 1
        return "".join(out)

    def double_quoted(self) -> str:
        self.i += 1
        out = []
        while self.i < len(self.text):
            c = self.text[self.i]
            if c == '"':
                self.i += 1
                break
            if c == "\\" and self.peek(1) in ('$', '`', '"', "\\", "\n"):
                if self.peek(1) != "\n":
                    out.append(self.peek(1))
                self.i += 2
            elif c == "$" and self.peek(1) == "(":
                out.append(self.substitution())
            elif c == "`":
                out.append(self.backtick())
            else:
                out.append(c)
                self.i += 1
        return "".join(out)

    def arithmetic(self) -> str:
        """`$(( … ))` or `(( … ))` as raw text: an expression, where `<<` shifts and starts nothing."""
        start, depth = self.i, 0
        while self.i < len(self.text):
            c = self.text[self.i]
            depth += (c == "(") - (c == ")")
            self.i += 1
            if depth == 0 and c == ")":
                break
        return self.text[start:self.i]

    def substitution(self) -> str:
        """`$( … )`, whose body is tokenized as commands of its own. Returns its raw text."""
        if self.text.startswith("$((", self.i):
            self.i += 1
            return "$" + self.arithmetic()
        start = self.i
        self.i += 2
        self.parse(")")
        return self.text[start:self.i]

    def backtick(self) -> str:
        start = self.i
        self.i += 1
        self.parse("`")
        return self.text[start:self.i]


def _substitutions_in(body: str) -> list[Command]:
    """The commands inside `$( … )` and backticks in text bash expands like a double-quoted string."""
    tokenizer = _Tokenizer(body)
    while tokenizer.i < len(body):
        c = body[tokenizer.i]
        if c == "\\":
            tokenizer.i += 2
        elif c == "$" and tokenizer.peek(1) == "(":
            tokenizer.substitution()
        elif c == "`":
            tokenizer.backtick()
        else:
            tokenizer.i += 1
    return tokenizer.found


def commands(text: str) -> list[Command]:
    """Every simple command in `text`, including those inside substitutions, in the order found."""
    tokenizer = _Tokenizer(text)
    tokenizer.parse(None)
    return tokenizer.found


SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
SSH_OPTIONS_WITH_VALUE = {"-b", "-c", "-D", "-E", "-e", "-F", "-I", "-i", "-J", "-L", "-l", "-m", "-O", "-o",
                          "-p", "-Q", "-R", "-S", "-W", "-w"}
_C_FLAG = re.compile(r"-[a-zA-Z]*c[a-zA-Z]*")


def tool_name(word: str) -> str:
    """A command word as the program it names: `/usr/bin/git.exe` is `git`."""
    return word.replace("\\", "/").rsplit("/", 1)[-1].lower().removesuffix(".exe")


def nested_scripts(argv: list[str], stdin: list[str]) -> list[str]:
    """Command text this command hands to another shell to run: an ssh remote command, the
    argument of `sh -c` or `eval`, a script a shell or ssh reads on stdin, a `find -exec`
    command, a `git submodule foreach` command. `argv` has already been through `command_argv`."""
    if not argv:
        return []
    tool = tool_name(argv[0])
    if tool == "ssh":
        i, host_seen, remote = 1, False, []
        while i < len(argv):
            if argv[i].startswith("-") and not remote:
                i += 2 if argv[i] in SSH_OPTIONS_WITH_VALUE else 1
            elif not host_seen:
                host_seen, i = True, i + 1
            else:
                remote.append(argv[i])
                i += 1
        if not remote:
            return list(stdin)
        remote_words = " ".join(remote).split()  # ssh joins its arguments with spaces for the remote shell
        reads_stdin = tool_name(remote_words[0]) in SHELLS and not any(_C_FLAG.fullmatch(w) for w in remote_words[1:])
        return [" ".join(remote)] + (list(stdin) if reads_stdin else [])
    if tool == "eval":
        return [" ".join(argv[1:])] if argv[1:] else []
    if tool in SHELLS:
        for i, word in enumerate(argv[1:], 1):
            if _C_FLAG.fullmatch(word):
                rest = [w for w in argv[i + 1:] if not w.startswith("-")]
                return rest[:1]
        return list(stdin)
    if tool == "find":
        scripts, i = [], 1
        while i < len(argv):
            if argv[i] in ("-exec", "-execdir", "-ok", "-okdir"):
                j = i + 1
                while j < len(argv) and argv[j] not in (";", "+"):
                    j += 1
                scripts.append(" ".join(argv[i + 1:j]))
                i = j
            i += 1
        return scripts
    if tool == "git" and argv[1:3] == ["submodule", "foreach"]:
        rest = [w for w in argv[3:] if w not in ("--recursive", "-q", "--quiet")]
        return [" ".join(rest)] if rest else []
    return []


def command_argv(argv: list[str]) -> list[str]:
    """The words of the command itself, with whatever stands in front of it removed."""
    argv = list(argv)
    while argv:
        head = argv[0]
        if "=" in head and head.split("=", 1)[0].isidentifier():
            argv = argv[1:]
            continue
        if head in RESERVED:
            argv = argv[2:] if head == "time" and argv[1:2] == ["-p"] else argv[1:]
            continue
        if head == "function":  # `function name { … }`: the body's first command follows
            argv = argv[2:]
            continue
        name = tool_name(head)
        if name not in WRAPPERS:
            break
        i, takes_value = 1, WRAPPERS[name]
        while i < len(argv) and argv[i] not in _WRAPPER_MARKERS.get(name, ()) and (
                argv[i].startswith("-") or (name == "env" and "=" in argv[i])):
            i += 2 if argv[i] in takes_value else 1
        if i < len(argv) and argv[i] in _WRAPPER_MARKERS.get(name, ()):
            i += 1
        if name in _TAKES_POSITIONAL and i < len(argv):
            i += 1
        argv = argv[i:]
    while argv and argv[-1] == "}":
        argv = argv[:-1]
    return argv
