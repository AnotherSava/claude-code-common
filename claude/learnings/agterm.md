# agterm

Things about agterm that its bundled skill does not cover. The skill itself is comprehensive; read it
first (`~/.claude/skills/agterm/SKILL.md`), and read this for the two facts it cannot carry.

## Do not edit the bundled skill — it is vendored, and your edit dies at the next upgrade

`claude/skills/agterm/` in the dotfiles repo is **vendored third-party content**, byte-identical to
`/Applications/agterm.app/Contents/Resources/agterm/`, shipped inside the Homebrew cask and **rewritten
in full on every `brew upgrade`**. It is deliberately gitignored (`claude/skills/*` with a whitelist of
the user's own skills) and declared in `claude/untracked-skills.local.txt` with that reason.

Three consequences:

- An edit there is silently reverted by the next cask upgrade, and breaks the byte-identity invariant
  meanwhile.
- It never appears in `git status`, because an ignored path does not — so no commit flow will mention it,
  and nothing will tell you the edit was lost.
- A note you want to keep about agterm belongs **here**, in a tracked learning, not in that file.

Restore it with `cp /Applications/agterm.app/Contents/Resources/agterm/SKILL.md ~/.claude/skills/agterm/SKILL.md`
and confirm with `diff` that the two are identical again.

The general shape, worth carrying beyond agterm: before editing anything under a `skills/` tree, check
whether that directory is tracked. `git ls-files --error-unmatch <dir>` answers it in one command, and
`git check-ignore -v <path>` names the rule and line that excludes it.

## `ok` from `session type` means accepted, not submitted

The documented way to send a message to another session is to type the text and then submit it:

```bash
tr -d '\n' < msg.txt | agtermctl session type --stdin --select --target <ID>
printf '\r'          | agtermctl session type --stdin --target <ID>
```

Both calls return `ok` — and the text can still be sitting unsent on the prompt line. Observed
2026-08-26 on a session receiving a long single-line brief: the paste arrived as a bracketed
`[Pasted text #N]` and the carriage return did not take. `ok` reports that the control socket accepted
the command, never that the program consumed the line.

So the send is not finished until you have looked:

```bash
agtermctl session text --target <ID> --lines 12
```

If the message is still on the `❯` prompt line rather than scrolled above it, send `\r` again. Two of
three sends took first time in that session and one did not, so this is intermittent — which means
verifying every send is the only reliable policy. It costs one command; skipping it costs a message the
other agent never receives while you believe it did.

Related: newlines in the payload each submit separately, so a multi-line brief becomes N premature
Enters — strip them (`tr -d '\n'`) and send one long line. The bundled skill covers that part.
