# Everyone admitted shares the data

For an app in which no record belongs to one person: the owner alone uses it, or a household or a team
works on one set of records. Sign-in then answers one question, whether this person may come in, and the
app's group at the sign-in service is where that is decided.

Nothing in the schema changes. This recipe adds a function that names the person, and the decision
written where the next session will read it.

## 1. Name the person, without a user table

The function every caller goes through returns the session itself:

```ts
import { headers } from "next/headers";

import { readSession } from "@/lib/signin";
import type { Session } from "@/lib/signin";

export async function requirePerson(): Promise<Session> {
  const session = readSession((await headers()).get("cookie"));
  if (!session) throw new Error("No session");
  return session;
}
```

The gate has normally answered before this runs. The throw is for a path the `matcher` in `proxy.ts`
left out.

## 2. Record who acted only where the user wants it

If the user wants a record to say who made or changed it, add a column for that and store `session.sub`,
which never changes; an address or a name can. Records written before sign-in keep what they hold. With
no such wish, add nothing.

## 3. Leave the per-deployment items as they are

A login for an outside service in the environment, an inbox, a token that opens a feed: each one serves
the whole app, as before, and every person admitted acts through it.

## 4. Write the decision into the app

In the app's `README.md`, or in its docs page on access where it has one, under the heading
**Who sees what**:

```
Everyone admitted to this app sees and can change all of its data. Admitting a person at the sign-in
service hands them all of it.
```

A later session reads that section before it admits anyone.

## When this stops fitting

When people should differ in what they may do, or a person should keep records of their own, run
**Settle whose data it is** again. It takes the recipe the new answers lead to, or stops where none
covers them.
