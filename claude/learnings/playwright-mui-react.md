# Playwright + MUI / React-controlled inputs

When automating a React app where inputs are controlled components (state lives in React, the DOM input mirrors that state), Playwright's `locator.fill()` or `input.fill()` often doesn't commit the new value to the app's internal state. The visible value updates briefly, but on the next render React overwrites it from state, or the next form submission reads the stale state.

**MUI `<TextField>`** (built on top of a native `<input>` with React's tracked-value mechanism) is the most common offender. Symptoms:

- `fill()` shows the new text in the input field during the session.
- A subsequent `input_value()` reads back the new text (DOM is updated).
- After "Save", the persisted value is the old one.
- Reloading the page shows the old value.

## Root cause

React tracks the input's value via a hidden setter installed on the DOM node. When *any* code (including Playwright via CDP) assigns to `input.value`, React's tracker sees the new value but *also* sees no React event was dispatched, so it does nothing. The next render overwrites DOM with the React state, which is still the old value.

The fix is to dispatch an `input` event React listens for — and to assign through the **native** value setter so the assignment isn't intercepted, then dispatch the event so React picks it up.

## Working pattern

```js
// Run inside page.evaluate(...) from Playwright
const el = document.querySelector("input[name='title']");
const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
nativeSetter.call(el, newValue);
el.dispatchEvent(new Event('input', { bubbles: true }));
el.dispatchEvent(new Event('change', { bubbles: true }));  // optional, some forms listen for this too
```

From Python/Playwright:

```python
page.evaluate("""(newValue) => {
    const el = document.querySelector("input[name='title']");
    if (!el) return false;
    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    nativeSetter.call(el, newValue);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return el.value === newValue;
}""", new_value)
```

For `<textarea>` use `HTMLTextAreaElement.prototype` instead of `HTMLInputElement.prototype`.

## When to try `fill()` / `type()` first

Plain `locator.fill()` works fine for:
- Uncontrolled inputs (most non-React sites).
- React inputs that internally call `onChange` from a real native `input` event — Playwright does dispatch `input` events for `fill()`, so simple controlled inputs work too.

It tends to fail on MUI's `TextField`, controlled inputs wired to Formik / react-hook-form when the form library has snapshot comparisons, and inputs inside re-mounting form panels (where the input element is replaced after the form's data loads). If `fill()` shows the right text but the save persists the old value, this is the pattern you need.

## Related quirk: form remounting

React/MUI forms often remount inputs after fetching their initial data, which means:

- `page.wait_for_selector("input[name='title']")` succeeds (element appears).
- `page.query_selector(...)` *immediately afterwards* may return the same element handle whose underlying node React then replaces.
- Subsequent operations on that handle may target a detached node.

Mitigation: insert a `page.wait_for_timeout(2000-3000)` after `wait_for_selector` to let the form data load and stabilize, then re-query. Alternatively, wait for a sentinel element that only appears once the form is fully populated (e.g. a specific value in a sibling input).

## CKEditor 5 has its own version of the same problem

For rich-text fields rendered by CKEditor 5, neither `fill()` nor the native-setter trick on the underlying `<div class="ck-content">` commits to CKEditor's internal model. The supported API is `editorEl.ckeditorInstance.setData(html)`:

```python
page.evaluate("""(html) => {
    const editorEl = document.querySelector('.ck-content[role="textbox"]');
    if (editorEl?.ckeditorInstance) {
        editorEl.ckeditorInstance.setData(html);
        return true;
    }
    return false;
}""", html_content)
```

The CKEditor instance is exposed on the editable DOM element after the editor mounts.
