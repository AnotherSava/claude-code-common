# Closing an npm audit finding that `npm audit fix` cannot reach

When `npm audit fix` exits 1 and still lists a transitive package as "fix available via `npm audit fix`", the
dependent usually pins a range that stops below the patched version. Running the fix again changes nothing,
because npm will not break a declared range without `--force`, and `--force` often installs a different
major of the *dependent* instead.

Measured 2026-11-11: `@typescript-eslint/typescript-estree@8.72.2` (also the latest release) declared `minimatch:
^10.2.2`, while the advisory covered `>= 7.0.0, < 11.0.1`. No release of the dependent allowed a fixed version.

## The fix: a scoped `overrides` entry, justified by the call sites

```json
"overrides": {
  "@typescript-eslint/typescript-estree": { "minimatch": "^11.0.1" }
}
```

Nest the override under the one dependent that needs it rather than overriding the package globally. A global
`"minimatch": "^11"` would also rewrite the `minimatch@3` that eslint and its plugins call with a different API.

Before you write it, check that the dependent's code still works against the new major. Grep its `dist/` for the
package and read each call, then compare those calls with the new major's changelog. In the measured case the only
call was `minimatch(path, pattern, { dot: true })`. minimatch 11 kept that call and removed `makeRe`, the `AST`
class and `matchOne`, so the override was safe. If the dependent used any of those removed APIs, it would have
failed at runtime with no warning at install time.

Then run `npm install` and check that `npm ls <pkg>` shows the overridden version under that dependent only. Run
`npm audit` and the project's real gate (lint, tests and build) after that. Remove the override once the dependent
releases a version that allows the fix, because a stale override pins a version nobody is tracking.

## A direct dependency's major bump: read the breaking-changes block

`npm audit fix --force` reports which major it would install for a direct dependency
(`Will install postal-mime@4.2.1, which is a breaking change`). Read the BREAKING CHANGES section of that
release's changelog instead of guessing. In the measured case (`postal-mime` 4) they were a Node version floor,
widened types and moved file paths, and none of those affects code that imports by package name on a current Node. Install the new
version with `npm install <pkg>@^<major>` rather than `--force`, so that only this one package moves.
