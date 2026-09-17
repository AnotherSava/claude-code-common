---
created: 2026-09-17 11:44:01
---

# Audit disable-model-invocation across the 46 global skills and set it on the side-effecting ones

State on 2026-09-17, measured across the 46 skills in `claude/skills/`:

- `pull` sets `disable-model-invocation: true` — decided this session, and the only skill that restricts invocation at all.
- `cleanup` and `deploy` set it to `false`. That is the documented default, so both lines are no-ops. Nothing records why they were written explicitly.
- Every other skill, `commit`, `publish` and `release` included, sets nothing and is therefore model-invocable.

Why it matters: `cleanup` describes itself as removing the app, its data and its caches from the system. The Claude Code docs name that exact class for the flag — "Use this for workflows with side effects or that you want to control timing, like /commit, /deploy, or /send-slack-message" — so a destructive skill Claude may start on its own judgement is the case the field exists to prevent.

Two costs pull against each other, both measured this session:

- Setting `true` keeps the description out of context. The docs table reads "Description not in context, full skill loads when you invoke" against the default "Description always in context". One description runs about 50 tokens, resident every session.
- Setting `true` also blocks Claude from invoking the skill when asked to. The Skill tool refuses outright and forbids hand-running the equivalent steps, so a flagged skill can only ever be typed by the user, and no other skill can delegate to it. That is why `commit` step 1 cannot hand its remote-sync work to `pull` and has to keep its own inline procedure.

Next step: go skill by skill and decide. The likely `true` set is the side-effecting and destructive ones — `commit`, `deploy`, `cleanup`, `publish`, `release`, `reset`, `pr-merge`, `github-create`, `transcrypt` — weighed against how often you want Claude able to run each on request. Check whether the explicit `false` on `cleanup` and `deploy` was deliberate before touching it. If a policy settles, consider whether a rule under `claude/conventions/rules/` can enforce it rather than leaving it to memory.
