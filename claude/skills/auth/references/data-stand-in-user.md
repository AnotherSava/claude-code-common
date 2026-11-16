# Records already keyed by a stand-in user

For an app whose schema already has a user table and a user column on each personal record, with
everything owned by one row the app made up: a stub the code looks up, or an owner the seed creates. That
row is the stand-in. Adoption hands it to a real person, gives every other person admitted a row of
their own, and removes the code that pretended.

Both shapes here were run in scratch projects on 2026-11-13, with the cases under **Test it in the
app**: Drizzle 0.45 on Postgres 17, and Prisma 7.10 on SQLite. Neither has been through an app's
adoption yet.

## 1. Check the starting point

1. The user table still holds the stand-in alone, as **Settle whose data it is** found. If a row has been
   added since, go back to that step.
2. Count what the stand-in owns in each personal table, to compare after the first sign-in.
3. Find every place that reaches the stand-in without going through the current-user function: a lookup
   by its fixed id or address, a query for the first row holding the owner role, a seed, a test helper.

## 2. Add the link to the user table

Add a `sub` column: text, unique, nullable. It holds the person's ID at the sign-in service and is null
only on a row that existed before sign-in did. Add a column for the address or the name only where the
app shows or uses the value; the stand-in's own columns take the real person's values at the hand-over.

```ts
// Drizzle
sub: text('sub').unique(),
```

```prisma
// Prisma
sub String? @unique
```

Generate the migration with the project's own command and read the SQL it wrote: one added column and
one unique constraint or index, nothing dropped.

## 3. Replace the current-user function

The function finds the person by `sub`. On a miss, the first sign-in the database has ever seen takes
over the stand-in row, and everyone after that gets a new row. The take-over is one conditional
statement, so two requests arriving together cannot both take the row, and it stops applying once any
row carries a `sub`.

Drizzle, with the app's own columns in `seen`:

```ts
import { and, eq, isNotNull, isNull, notExists } from 'drizzle-orm';

export async function getCurrentUser(): Promise<typeof users.$inferSelect> {
  const session = readSession((await headers()).get('cookie'));
  if (!session) throw new Error('No session');
  const known = await db.query.users.findFirst({ where: eq(users.sub, session.sub) });
  if (known) return known;
  const seen = { sub: session.sub, email: session.email, displayName: session.name };
  // The first sign-in this database ever sees takes over the row that held everything until now. Once any
  // row carries a sub the condition is false for good, so nobody later can take a row that is not theirs.
  const nobodyYet = notExists(db.select({ id: users.id }).from(users).where(isNotNull(users.sub)));
  const [inherited] = await db.update(users).set(seen).where(and(isNull(users.sub), nobodyYet)).returning();
  if (inherited) return inherited;
  const [created] = await db.insert(users).values(seen).onConflictDoNothing({ target: users.sub }).returning();
  if (created) return created;
  const [raced] = await db.select().from(users).where(eq(users.sub, session.sub));
  return raced;
}
```

Prisma, with the table and column names as the migration wrote them:

```ts
export async function getCurrentUser(): Promise<User> {
  const session = readSession((await headers()).get("cookie"));
  if (!session) throw new Error("No session");
  const known = await prisma.user.findUnique({ where: { sub: session.sub } });
  if (known) return known;
  // The first sign-in this database ever sees takes over the row that held everything until now. Once any
  // row carries a sub the condition is false for good, so nobody later can take a row that is not theirs.
  await prisma.$executeRaw`UPDATE "User" SET "sub" = ${session.sub}, "name" = ${session.name} WHERE "sub" IS NULL AND NOT EXISTS (SELECT 1 FROM "User" WHERE "sub" IS NOT NULL)`;
  return prisma.user.upsert({ where: { sub: session.sub }, update: {}, create: { sub: session.sub, name: session.name } });
}
```

Both snippets leave out the app's own imports: its database handle, its schema or client types, and
the `headers` and `readSession` that **Wire the app** shows.

- With no session the function throws, and a route handler answers 401. It never falls back to the
  stand-in.
- Delete the stub and the fixed id or address it used, in the same change. Keep a seed that creates the
  stand-in only where the section on roles says the app needs one.
- Point every place found in **Check the starting point** at this function.

## 4. Roles, where not everyone may change the shared records

Skip this section when **Settle whose data it is** found nothing that only some people may do.

1. Add a `role` column to the user table, with the least role as its default (`member`), and give the
   stand-in the top role (`owner`) in the same migration. It is the only row there.
2. One function beside the current-user function (`requireOwner`) throws unless the person holds the top
   role. Every action that changes a shared record calls it, and so does every admin page.
3. A database with no user rows needs someone to take the top role. Keep a seed that creates the stand-in
   with that role, which the first sign-in then takes over, or have the function give the top role to
   the first row it creates. Keep whichever the app already has.
4. A later change of role is one statement against the database, by hand. Build no page for it until the
   user asks for one.

## 5. Scope every read and write

Enumerate every query on a personal table; do not sample. For each one:

- a list filters by the current user's id;
- a lookup by an id from a URL, a form or an action's argument carries the user's id in the same
  condition, so another person's record reads as missing;
- an insert takes the user column from the current user, never from the request;
- a uniqueness rule meant per person includes the user column.

Records the decision marked shared take no filter. Their writes take the role check where roles exist.

## 6. Carry out what was decided for the per-deployment items

A login for an outside service kept in the environment, or a token in a settings table with no user
column, acted for the stand-in. After adoption it acts for whoever triggers the code that uses it. For
each item **Settle whose data it is** listed:

- it stays the owner's: the actions that use it take the role check;
- everyone admitted acts through it: say so in the app's **Who sees what** section.

## 7. Write the decision into the app

In the app's `README.md`, or in its docs page on access where it has one, under the heading
**Who sees what**, with the kinds of record as the app's own docs name them:

```
Everyone admitted to this app shares: <the shared kinds>.
Each person keeps their own: <the personal kinds>.
Only the owner may: <what the role check guards>.
```

Leave out a line that has nothing to list.

## 8. Test it in the app

Add these to the app's own test suite, against its real schema, and run the project's gate:

- the first sign-in on a database holding only the stand-in gets the stand-in's id and its records;
- the same person is found again by `sub`;
- a second person gets a row of their own, the least role, and none of the first person's records;
- the second person cannot read, change or delete one of the first person's records by its id, and the
  record is unchanged afterwards;
- a row without a `sub`, created after the first sign-in, is not handed to the next new person.

Then prove the tests can fail: remove the nobody-has-signed-in-yet condition from the take-over and run
them again. The last case must fail. Restore the condition.

## 9. At the first production sign-in

- Admit nobody but the person who inherits until they have signed in once. Whoever arrives first takes
  the stand-in.
- After that sign-in they see the records that existed before, and the counts from **Check the starting
  point** stand unchanged under their row.

## A development database copied from production

Its rows carry production `sub` values, which no development session has, since `AUTH_DEV_USER` signs
in with a `sub` of `dev:` followed by the address. Where the user table keeps addresses unique, the
development session is refused on a duplicate address. Where it does not, the session gets a new, empty
row and says nothing. In the step that makes the copy, rewrite each copied row's `sub` to the
development form:

```sql
UPDATE users SET sub = 'dev:' || email;
```

## A person re-created at the sign-in service

They arrive with a new `sub`. Point their existing row at it by hand. Until then a unique address
refuses them, and without one they start over with an empty row.
