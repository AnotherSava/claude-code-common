# React hydration warnings from attributes the browser stamps

Some browsers and extensions add their own attributes to the DOM after the server's HTML arrives and before React
hydrates. React compares attributes during hydration, finds ones the server never rendered, and reports "A tree
hydrated but some attributes of the server rendered HTML didn't match the client properties". In Next's dev server
that is the red "1 Issue" badge. Attribute mismatches are not patched up and change nothing visible; the warning is
dev-only.

Known stampers:

| Who | Elements | Attribute |
|---|---|---|
| Chrome on iOS | `<html>` | `__gcrremoteframetoken` |
| Chrome on iOS | `<form>`, and text-like `<input>` such as a read-only URL box | `__gcruniqueid` |
| Grammarly and similar extensions | `<body>` | their own data attributes |

Observed 2026-11-06 on a Next 16 / React 19 app: the `<form>` stamps showed up first (38 of them). After those were
silenced, the next reload reported `<html>` and one `<input>`. So fix the whole set at once, not only the element
the first report names.

## Fix

`suppressHydrationWarning` ignores attribute differences on the element that carries it, and on nothing inside it.
One flag on a parent does not cover its children. So it has to be on each element that gets stamped:

- `<html>` and `<body>` in the root layout
- every form and form field, through one set of wrapper components, so a new form cannot miss it:

```tsx
import type { ComponentProps } from 'react';

export function Form(props: ComponentProps<'form'>) {
  return <form {...props} suppressHydrationWarning />;
}
export function Input(props: ComponentProps<'input'>) {
  return <input {...props} suppressHydrationWarning />;
}
// Select and Textarea the same way
```

With no `'use client'` directive, the wrappers work in both server and client components. React 19 passes `ref` as
an ordinary prop, so the spread keeps refs working.

## Finding which elements are stamped

Next 16's dev server forwards browser console errors to its terminal output with a `[browser]` prefix, diff
included: lines starting with `-` are attributes the client has and the server did not render. Grep the dev
server's log for the attribute and the element above it, rather than asking for a screenshot of the overlay:

```bash
grep -B4 "^-  *__gcr" dev-server.err.log | grep -E "^ *<[a-z]+|__gcr"
```

Related: `nextjs-ssr-hydration-locale-sort.md`, a mismatch the app itself causes.
