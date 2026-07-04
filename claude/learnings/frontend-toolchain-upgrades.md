# Frontend Toolchain Major-Upgrade Gotchas

Non-obvious breakages hit when upgrading a Vite + TypeScript + Vitest project's dev dependencies to current majors (discovered June 2026: TS 5→6, Vite 6→8, Vitest 3→4, jsdom 28→29, npm 11 pin, GitHub Actions off Node 20). The failures are cryptic; the fixes are small once you know them.

## TypeScript 6 — side-effect imports of non-code modules now error (TS2882)

`import "./styles.css";` (or any side-effect import of a module without type declarations — CSS, etc.) compiled fine under TS ≤5 but fails under **TS 6**:

```
error TS2882: Cannot find module or type declarations for side-effect import of '../games/azul/styles.css'.
```

A Vite project that never added the Vite client types relied on TS being lenient here. Fix: add the standard ambient declaration (a one-liner) that declares `*.css`, image, and other asset modules:

```ts
// src/vite-env.d.ts
/// <reference types="vite/client" />
```

Make sure it's covered by tsconfig `include` (`"src/**/*.ts"` includes `*.d.ts`). A narrower alternative is `declare module "*.css";`, but `vite/client` is the idiomatic, comprehensive fix.

## Vitest 4 — mocks are constructed via their implementation on `new`

A mock used as a constructor must have a **constructable** implementation in Vitest 4. This works in Vitest 3 but throws in 4:

```ts
globalThis.OffscreenCanvas = vi.fn(() => ({ getContext: () => mockCtx })); // arrow impl
// code under test: new OffscreenCanvas(w, h)
// Vitest 4: TypeError: () => ({ getContext: ... }) is not a constructor
```

Vitest 4 invokes the mock's implementation *as a constructor* (`new impl()`) when the mock is `new`-ed; arrow functions can't be constructed. Use a regular `function` (constructable; returning an object overrides `this`):

```ts
globalThis.OffscreenCanvas = vi.fn(function () { return { getContext: () => mockCtx }; });
```

The symptom is an "X is not a constructor" *unhandled error* plus a cascade of "expected spy to be called" assertion failures in tests that exercise the `new`-ed mock.

## esbuild + npm 11 `allow-scripts` warning is benign

Recent npm (11.x) blocks some dependencies' lifecycle scripts by default and warns:

```
npm warn allow-scripts esbuild@0.25.x (postinstall: node install.js)
npm warn allow-scripts Run `npm install-scripts ls` to review, or `... approve <pkg>` to allow.
```

This looks alarming for esbuild (which needs a native binary), but esbuild still works: the binary ships via **`optionalDependencies`** (`@esbuild/<platform>-<arch>`), not the postinstall — `install.js` only validates/links. A clean `npm ci` + `vite build` + `vitest` succeeds without approving the script. Don't chase it; confirm with a fresh CI `npm ci` rather than allow-listing.

## GitHub Actions on Node 20 are deprecated — bump majors, but verify inputs first

`actions/checkout@v4`, `actions/setup-node@v4`, `actions/upload-artifact@v4`, `actions/download-artifact@v4` run on Node 20 (GitHub forces them onto Node 24 with a deprecation annotation, pending removal). Latest majors use Node 24: checkout **v7**, setup-node **v6**, upload-artifact **v7**, download-artifact **v8** (each action versions independently — mismatched major numbers are normal).

Before a multi-major jump, confirm the inputs your workflow uses still exist in the target major (don't assume):

```bash
gh api repos/actions/<name>/contents/action.yml?ref=v<N> --jq '.content' | base64 -d | grep -iE "node-version-file|cache|pattern|merge-multiple|retention-days"
```

Then push to a branch (no tag) so the build job validates the new versions; a release/tag-gated job won't be exercised by a branch push, so its actions (e.g. download-artifact in a release job) only get tested on the next tagged release.

## Node version: stay on LTS, don't chase the newest

A newly-released even major isn't LTS until that October (Node 26 released ~April 2026, becomes LTS ~Oct 2026). For a shipped project, keep `.nvmrc` / `engines.node` / `@types/node` on the **active LTS** (Node 24 through 2026) rather than the current release.
