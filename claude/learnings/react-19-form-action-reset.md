# React 19 resets a form after its action, and an uncontrolled select snaps back

A `<form action={serverAction}>` in React 19 is reset automatically once the action completes (the
`requestFormReset` behaviour that comes with form actions). For uncontrolled fields that reset restores each
field's *default*, and for a `<select defaultValue>` the default React holds is the one from mount, not the
one from the latest render.

## What was measured

React 19.2.8, `react-dom-client`'s update path for `select` (`updateProperties`, case `"select"`): the options'
`defaultSelected` flags are recomputed only when the `multiple` prop changes. A changed `defaultValue` on a
re-render touches no option. So after a server action saves a new value and the page re-renders with it as
`defaultValue`, the post-action `form.reset()` puts the select back on whatever was stored when the page
loaded, in both directions. Reproduced in a jsdom harness against the installed React: mount with
`defaultValue=7`, select 1, re-render with `defaultValue=1`, `form.reset()` shows 7.

The save itself succeeded; only the control lies about it, and reloading the page shows the right value. That
is what makes it easy to misdiagnose as a failed write.

## The fix

Key the select on the stored value, so a changed value remounts it and the mount-time default is the new one:

```tsx
<select key={weekStart} name="weekStart" defaultValue={weekStart}>
```

A controlled select (`value` plus state) also works, but it turns a server-rendered form into a client
component for no other reason.

## Not established

Whether `<input type="checkbox" defaultChecked>` has the same problem was not measured. React does write
`defaultChecked` through on update for inputs, so it is probably fine, but check before relying on it.
