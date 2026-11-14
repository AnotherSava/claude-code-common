# React forms: stopping a submit, telling a paste from typing, and a field hidden with `visibility`

Measured 2026-11-14 with react-dom 19.2.8 in Chrome 157, headless and driven through CDP. React's development and
production builds gave the same results throughout.

## Calling `preventDefault` in `onSubmit` stops a function `action`

**To turn a submit into something else, call `event.preventDefault()` in the form's `onSubmit`.** A form whose
action is a function, or the dispatcher that `useActionState` returns, calls `onSubmit` first and runs the action
only when the event was not prevented. A submit button's own `formAction` is skipped the same way.

That makes `onSubmit` the place to divert Enter in a text field, with no `onKeyDown` handler:

```tsx
const onSubmit = (event: FormEvent<HTMLFormElement>) => {
  if (!needsLookup(fields.title)) return; // the action runs
  event.preventDefault(); // the action does not run
  void lookUp(fields.title);
};
<form action={submit} onSubmit={onSubmit}>…</form>
```

Enter in a text field and a click on the submit button behaved alike:

| What `onSubmit` does | The action | `useFormStatus().pending` | Uncontrolled fields |
|---|---|---|---|
| returns | runs | true until the action settles | reset afterwards |
| calls `preventDefault()` | does not run | stays false | keep what was typed |
| calls `preventDefault()` and starts a transition | does not run | true until the transition settles | keep what was typed |

In the transition case React marks the form pending for the transition the handler started, and still never calls
the action. A handler that wants the fields cleared calls `requestFormReset(form)` inside that transition, which
reset them when tried. The reset that follows an action is the subject of `react-19-form-action-reset.md`.

The check is in `react-dom-client`. The listener React queues for a form's `submit` event opens by testing
whether `nativeEvent.defaultPrevented` is set, and that branch never calls the action.

## Reading `inputType` in `onChange` to tell a paste from typing

**Act at once on a paste or a drop, and wait for blur or submit when the text is typed.** Text typed one character
at a time passes through values that are valid and wrong: a link ending in `/boardgame/224517` is first a link
to `/boardgame/22`. React calls a text input's `onChange` for the native `input` event, so that event's input
type says how the text arrived. Read it as `(event.nativeEvent as InputEvent).inputType`:

| How the text arrived | `inputType` | `data` |
|---|---|---|
| a key press | `insertText` | the character |
| Backspace | `deleteContentBackward` | `null` |
| Ctrl+V | `insertFromPaste` | the pasted text |
| text dragged onto the field | `insertFromDrop` | the dropped text |

A paste goes in at the caret, so `event.target.value` is the whole field, with what was already there, and `data`
is the piece that arrived. Only these four ways were measured. Counting every other `inputType` as typing is the
safe default, since a wrong guess costs no more than waiting for blur.

## A field hidden with `visibility: hidden` still submits and still validates

**While a field is hidden with `visibility: hidden`, keep its value empty and leave `required` off it.** Hiding a
row this way reserves its space, so a dialog keeps its size when the row appears, and takes the field out of the
tab order and the accessibility tree. The form goes on treating it as a field.

Measured on an `<input>` inside a `<label>` styled `visibility: hidden`:

- **Layout:** the row and the input kept their boxes, and the button after the row sat where it sits with the row
  visible.
- **Focus:** Tab went from the field before the row to the button after it. Neither `focus()` nor a click where
  the input sits focused it.
- **Accessibility tree:** Chrome reported the input and its label as ignored, with the reason `notVisible`.
- **Submission:** the field and its value were in `new FormData(form)` and in the `FormData` the action received.
  An input under `display: none` was sent as well. A `disabled` input was left out.
- **Validation:** with `required` and an empty value, the form could not be submitted. Enter, the submit button
  and `form.requestSubmit()` each did nothing, `onSubmit` was not called, and the one trace was a console error
  reading `An invalid form control with name='link' is not focusable.` With `noValidate` on the form it submitted.

The same property reserves a label's width in `css-layout-gotchas.md`.
