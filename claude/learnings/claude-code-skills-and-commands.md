# Skills and slash commands are one feature, and who may invoke is frontmatter

Researched 2026-09-17 against the live docs, the `claude-code` CHANGELOG, and Anthropic's own plugin
repositories. Read this before deciding whether something should be a skill or a `commands/` file, and
before putting an invocation-control flag on anything.

## They were merged, and the older format is not the recommended one

The CHANGELOG entry for v2.1.3 (npm publish 2026-01-09) reads, in full:

> Merged slash commands and skills, simplifying the mental model with no change in behavior

The documentation followed. The old slash-commands URL now 301-redirects to a page titled *Extend
Claude with skills*, whose intro note says:

> **Custom commands have been merged into skills.** A file at `.claude/commands/deploy.md` and a skill
> at `.claude/skills/deploy/SKILL.md` both create `/deploy` and work the same way. Your existing
> `.claude/commands/` files keep working.

and whose bullet on the older layout says:

> **Command files**: a Markdown file in `.claude/commands/` is the older format and still works. It
> supports the same frontmatter except `name` and `paths`. … Prefer a skill for new work, since skills
> also support supporting files.

The built-in commands reference no longer documents authoring one at all — its whole guidance is "To
add your own commands, see skills". Where a skill and a same-named command file collide, the skill wins.

**Mind the wording when quoting this.** The docs never say *deprecated* or *legacy*; the strongest
phrases are "the older format" and "New commands should usually be skills instead; commands remain
supported". Anthropic's own artifacts are blunter — a plugin-repo commit titled
`docs(plugin-dev): deprecate commands/ in favor of skills/<name>/SKILL.md` (2026-03-17), teaching
material calling the directory "a legacy format", and a `commands_DEPRECATED` loader tag inside the
shipped binary. Both readings are defensible; do not attribute the harder one to the documentation.

Practical consequence: a new `/name` is a skill. The only functional thing a command file cannot do is
carry a directory of supporting files, set `name`, or set `paths`.

## Who may invoke is a frontmatter field, not a choice of directory

This is the axis people still think is commands-vs-skills. It is not; it is two fields on a skill.
The docs table, verbatim:

| Frontmatter | You can invoke | Claude can invoke | When loaded into context |
| :--- | :--- | :--- | :--- |
| (default) | Yes | Yes | Description always in context, full skill loads when invoked |
| `disable-model-invocation: true` | Yes | No | Description not in context, full skill loads when you invoke |
| `user-invocable: false` | No | Yes | Description always in context, full skill loads when invoked |

The stated case for each:

- `disable-model-invocation: true` — "Use this for workflows with side effects or that you want to
  control timing, like `/commit`, `/deploy`, or `/send-slack-message`."
- `user-invocable: false` — "for background knowledge that isn't actionable as a command", the example
  being a `legacy-system-context` skill.

## `disable-model-invocation: true` blocks the agent completely, not just auto-firing

This is the part that surprises, and it cost a promise on 2026-09-17: having written a flagged `/pull`
skill and been asked to run it, the Skill tool refused outright —

```
Skill pull cannot be used with Skill tool due to disable-model-invocation.
Ask the user to run /pull themselves — it cannot be invoked via the Skill tool.
Do not replicate this skill's workflow by other means — it is reserved for explicit user invocation.
```

So the flag means three things at once, and only the first is obvious:

1. Claude will not start it on its own judgement.
2. Claude cannot start it **when directly asked to** either.
3. Claude is barred from hand-running the equivalent steps, so there is no sanctioned workaround.

It follows that **no skill can delegate to a flagged skill**. A `/commit` that wants to sync a behind
remote cannot hand that off to a flagged `/pull`; it has to keep its own inline copy of the procedure.
Weigh that duplication before flagging anything other skills would want to call.

## What the flag actually saves in context

Only the description, and only while the skill is not invoked — the body never loads until invocation
under any setting. A one-sentence description measured 205 characters, roughly 50 tokens, resident per
session. So the context argument is real but small; decide on the side-effect risk instead, and treat
the token saving as a tiebreaker.

There is no middle setting. "Claude may invoke it only when explicitly asked" does not exist — the
fields are binary, so the choice is between an agent that can never run it and one that may decide to.
