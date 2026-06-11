# Adopting ruff on an existing Python codebase

Playbook distilled from retrofitting ruff onto a ~900-violation codebase (build123d-models, 2026-06). The governing principles live in global CLAUDE.md ("Best-Practice Adoption"); this file holds the concrete mechanics.

## Workflow

1. **Measure per rule-set before enabling anything**: `ruff check . --select <RULES> --statistics`. Decide per rule family from the real baseline, not from rule descriptions. Split measurements by `src` vs `tests` — the verdict often differs.
2. Enable a family only with a **clean baseline**: auto-fix what's safe, hand-fix what's real, and scope (per-file-ignores / option whitelists / inline `noqa` with reasons) what's intentional. Never enable with open violations.
3. Document every deliberately disabled rule and its reason **inside ruff.toml** — the config is where the next reader looks.
4. Wire a PostToolUse hook so the linter runs on every edited file (see `claude-code-integration.md` → "PostToolUse enforcement hooks").

## Rule-family verdicts and mechanics

| Family | Notes |
|---|---|
| `F` (full) | Always. `F821` undefined-name finds real latent bugs (here: an unreachable line referencing a renamed variable). Don't cherry-pick F401/F841 only — that silently drops F821. |
| `E4`,`E7`,`E9` | Cheap, real findings (bare except, ambiguous `l`). |
| `B` bugbear | Small baselines, genuine bugs (mutable `Vector()` default arg, `assert False` erased by `-O`). |
| `I` isort | Automates import-order conventions. See line-length interplay below. |
| `W` | Includes `W292` (newline at EOF) — often matches an existing style rule. |
| `ANN` | See retrofit strategy below. |
| `SLF001` | See friend-surface strategy below. |
| `B905` | `zip(strict=)`. Don't blanket-ignore: annotate per site — `strict=False` + comment on pairwise `zip(xs, xs[1:])` idioms (intentionally length-unequal), `strict=True` on same-length-by-construction zips (turns the invariant into an enforced one). |
| `E501` | Useless at conventional limits for a long-single-line codebase; useful as a **tripwire**: set `line-length` above the longest intentional line (zero baseline) so it only catches pathological generated lines. |
| formatter | Skip entirely when the project has a hand-maintained layout: it can't express conditional style rules and collapses aligned trailing comments to two spaces. |

## ANN retrofit strategy (911 → 0 in one pass)

- `ruff check --fix --unsafe-fixes --select ANN` auto-adds `-> None` wherever no return exists — covered ~70% (test methods, `__post_init__`, mutating helpers).
- Per-file-ignore `ANN001/ANN002/ANN003` in `tests/**`: annotating parameterized-injected test args is churn; return types stay enforced.
- `ignore = ["ANN401"]`: duck-typed boundaries (`export(*shapes)`, `fuse(*args)`) deserve an honest `Any`, not a decorative recursive union. Revisit ANN401 only if a type checker is adopted.
- The remainder is mechanical inference by pattern: fluent methods → `'ClassName'`, dimension properties → `float`, builders → the solid type.

## SLF001 friend-surface strategy

Ruff's SLF001 exempts only literal `self`/`cls` — it flags idiomatic sibling-instance access (`copy()` field transfer, `cls.__new__` constructors, same-module collaborator classes), unlike pylint's class-aware W0212. Resolution:

```toml
[lint.flake8-self]
extend-ignore-names = ["_top", "_build", "_orientation", ...]  # the friend-access surface, by member name
```

plus inline `# noqa: SLF001 — <reason>` on deliberate foreign-library reach-ins (kept at the call site because they're exceptional, not policy). Anything outside the named surface still flags.

## line-length drives more than E501

`line-length` also controls **isort's wrapping when auto-fixing**: at the default 88, I001 fixes rewrap imports into parenthesized multi-line blocks, and the magic trailing comma then pins them there forever. For a single-line-style codebase set both:

```toml
line-length = 320

[lint.isort]
split-on-trailing-comma = false   # lets --fix re-join previously wrapped blocks
```

## Landmines

- **Expected-output fixtures**: test data that is byte-compared against a generator/emitter output (e.g. emitted-code `.py` fixtures) must be `exclude`d — auto-fix "cleans" their deliberate unused imports and breaks the comparison test. Caught only by running the test suite after fixing: always run tests after every `--fix` wave.
- **Unsafe fixes remove whole statements** (F841): fine for pure expressions, review when the RHS could have side effects.
- A syntax error in one file silently shields it from `--fix` — re-run after repairing.
