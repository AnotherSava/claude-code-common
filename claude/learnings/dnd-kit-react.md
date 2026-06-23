# dnd-kit in React / Next.js

Recipes and gotchas for `@dnd-kit/core` drag-and-drop in React 19 / Next.js App Router, from building a "drag a row from one container to another" feature. For a simple move-between-containers UI you only need `@dnd-kit/core` — `@dnd-kit/sortable` is for reorder-within-a-list, which you can skip when within-container order is derived (e.g. always sorted by date).

## SSR hydration mismatch — give `DndContext` a stable `id`

Without an explicit `id`, dnd-kit generates accessibility ids (`aria-describedby="DndDescribedBy-N"`) from an internal counter that increments differently during the server render vs. the client render. Every draggable then mismatches on that attribute and React throws a hydration error on first paint:

> A tree hydrated but some attributes of the server rendered HTML didn't match… `aria-describedby="DndDescribedBy-0"` (server) vs `"DndDescribedBy-3"` (client)

Fix is one prop — a stable string makes the id deterministic (`DndDescribedBy-<id>`) on both sides:

```tsx
<DndContext id="inventory-dnd" sensors={sensors} ...>
```

## Drag only from the non-interactive parts of a row (custom sensor)

Making a whole row draggable (grab anywhere) conflicts with inputs/buttons inside it: a press-and-drag to select text in a field starts a drag instead. A distance threshold alone doesn't fix it (it only saves *clicks*, not drag-selects). The clean fix is a custom sensor whose activator refuses to start when the press lands on an interactive element:

```tsx
function isInteractive(target: EventTarget | null): boolean {
  return target instanceof Element &&
    target.closest("input, textarea, select, button, a, label, [contenteditable='true']") != null;
}
class RowPointerSensor extends PointerSensor {
  static activators = [{
    eventName: "onPointerDown" as const,
    handler: ({ nativeEvent: e }: React.PointerEvent) =>
      e.isPrimary && e.button === 0 && !isInteractive(e.target),
  }];
}
const sensors = useSensors(useSensor(RowPointerSensor, { activationConstraint: { distance: 8 } }));
```

`closest(...)` walks up from the pressed element; the draggable container is a `<div>` so it never matches — a press on "empty" row area activates, a press on a control doesn't. Do **not** filter on `role="button"`: dnd-kit's own `attributes` put `role="button"` on the draggable node itself, so filtering by role would disable the whole thing. Filter by tag name only.

Match the grab affordance to where a drag can actually start — `cursor: grab` on the draggable, but let inner controls keep their own cursor so the hand only shows over the handle area:

```css
.bdrag { cursor: grab; touch-action: none; }
.bdrag:active { cursor: grabbing; }
.bdrag input { cursor: text; }
.bdrag a, .bdrag button { cursor: pointer; }
```

`touch-action: none` on the draggable is needed for touch drags (prevents the scroll gesture from stealing the pointer).

## Optimistic cross-container move with `useOptimistic` (no mirror effect)

For a server-action move that reflows the UI, project the move optimistically and let it auto-revert to authoritative props after the action's revalidation lands. `useOptimistic` does exactly this when the update runs inside the same transition as the action:

```tsx
const [items, applyMove] = useOptimistic(serverItems, (state, mv) => /* return moved projection */);
const onDragEnd = (e) => {
  const toId = e.over?.id, data = e.active.data.current;
  if (!toId || data.fromId === toId) return;
  startTransition(async () => {
    applyMove({ id: data.id, fromId: data.fromId, toId });   // instant
    await moveOnServer(data.id, toId);                         // revalidatePath inside
  });                                                          // reverts to fresh props after
};
```

Do **not** reach for a `useState` mirror synced via `useEffect(() => setMirror(props), [props])` — the ESLint rule `react-hooks/set-state-in-effect` rejects setState-in-effect, and `useOptimistic` is the idiomatic replacement anyway. Recompute any *derived* fields (totals, "is empty" flags) inside the projection so dependent UI stays honest during the optimistic window.

## DragOverlay vs. transform

Render the floating element with `<DragOverlay>` and dim the source (`opacity` on `.is-dragging`) rather than applying `transform` to the original — the overlay tracks the cursor and the source stays in layout, which reads better for "lift and move to another container."

## Testing dnd-kit programmatically

dnd-kit's `PointerSensor` listens to **pointer events**. The chrome-devtools MCP `drag` tool dispatches **native HTML5 drag events**, which dnd-kit ignores — a `drag` call appears to do nothing. To drive a drag in a test, dispatch real `PointerEvent`s via `evaluate_script`: `pointerdown` on the source, several `pointermove`s that cross the `activationConstraint.distance`, then `pointerup` over the target (see `chrome-devtools-mcp.md`). Synthetic events work because dnd-kit doesn't check `isTrusted`.
