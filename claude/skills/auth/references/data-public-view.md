# Public pages that show the owner's records

For an app of the open shape whose public pages render the owner's own records: a library, a reading
list, a diary anyone may read. Use it together with the recipe for the records themselves. Where a
stand-in owns them today, that recipe is `data-stand-in-user.md`. Anyone else admitted may keep records
of their own, which no public page shows.

A request to such an app involves two people who are often not the same: the one signed in, who may be
nobody, and the one whose records the page shows. Every rule here keeps the two apart.

## 1. Two functions, never one

- **The signed-in person**: the current-user function from the records' recipe, in two forms. Pages use
  one that returns null with no session; writes use the one that throws.
- **The displayed person**: whose records this page shows. While only the owner's records are public, it
  returns the user holding the top role.

Reads on a public page filter by the displayed person. Writes act as the signed-in person, on that
person's own records only. Neither function calls the other.

## 2. Let the gate refuse a write that has no session

Wire the gate with the pattern **Wire the app** gives for the open shape, so that a write is refused
before any action runs.

- Keep the app's switch for closing its public pages, where it has one. With the switch off, pass the
  gate an empty list.
- The gate stays the outer check. Each action still asks who is signed in, and changes only that
  person's records.

## 3. Show a control only to the person it works for

A page shows its editing controls when the signed-in person is the displayed person. The check inside
the action is what enforces that. Hiding the control keeps the page from offering what would be refused.

## 4. Keep one person's view out of a shared cache

What a public page shows of the displayed person is the same for every visitor and may be cached.
Anything computed from the signed-in person is theirs alone: a cached function takes that person's id as
an argument, or is not cached.

## 5. Test it in the app

- with no session, a public page answers 200 and shows the displayed person's records, and a write to it
  answers 401;
- signed in as the displayed person, the controls are there and a change is saved;
- signed in as someone else, the page still shows the displayed person's records, with no controls, and
  an action aimed at one of those records by its id changes nothing;
- signed in as the displayed person again afterwards, the page shows nothing the other session put
  there.

## When this stops fitting

When a person besides the owner should have public pages of their own, run **Settle whose data it is**
again. It takes the recipe the new answers lead to, or stops where none covers them.
