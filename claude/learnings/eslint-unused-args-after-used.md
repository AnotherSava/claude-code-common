# `no-unused-vars` reports a parameter only when nothing after it is used

`@typescript-eslint/no-unused-vars` defaults to `args: "after-used"`. That does **not** mean "report every unused
parameter" — it reports only those sitting *after the last used one*. So two functions with identical intent get
opposite verdicts:

```ts
// passes: `_previous` is unused, but `formData` after it IS used
async function createEvent(_previous: Result | null, formData: FormData) { … }

// fails: both trailing parameters are unused, so both are reported
async function refreshEvent(slug: string, _previous: Result | null, _formData: FormData) { … }
```

The difference is decided by whether a *later* parameter happens to be used — nothing about the parameter being
complained about. That makes it look arbitrary, and it strands a codebase that has already adopted the leading
underscore convention: the underscore means nothing to the default config, and passes only by accident.

## Where it bites: React `useActionState`

An action is always invoked as `(previousState, formData)` whether or not it wants either. Bind extra arguments
in front and the unwanted ones end up trailing, which is exactly the reported position:

```tsx
// page (server): the only argument the action needs is `slug`
<Refresh action={refreshEvent.bind(null, slug)} />

// component (client)
const [result, submit, pending] = useActionState(action, null);
<form action={submit}>…</form>
```

The signature cannot be shortened — `useActionState` decides it — so the parameters have to exist and have to be
ignored.

## Fix: make the underscore mean something

```js
{
  rules: {
    "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
  },
}
```

Keep the severity the inherited config already used; a project running `eslint --max-warnings=0` fails on a
warning anyway, and raising it to `error` changes behaviour for anyone running eslint bare.

This **loosens** rather than disables — verify that with a probe rather than assuming, because "I turned the rule
down and the errors went away" is indistinguishable from having switched it off:

```ts
export function probe(used: string, forgotten: string, _deliberate: string): string { return used; }
// still reported:
//   'forgotten' is defined but never used. Allowed unused args must match /^_/u
```

Related options, same shape: `varsIgnorePattern`, `caughtErrorsIgnorePattern`. Add them only when something in
the codebase actually needs them — a loosened rule nobody needed is a rule nobody is checking.
