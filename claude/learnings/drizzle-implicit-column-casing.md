# Drizzle: `casing` must be set on the runtime instance, not just in the config

A defect that type-checks, lints, passes every test, and then fails on the **first real query**. Found August
2026; cost nothing only because a review caught it before deploy.

## The setup

Drizzle lets you declare a column without naming it:

```ts
export const bookings = pgTable('bookings', {
  confirmationCode: text(),          // bare — no explicit column name
});
```

and derive the SQL name from a casing strategy in `drizzle.config.ts`:

```ts
export default defineConfig({
  schema: './src/db/schema.ts',
  casing: 'snake_case',
});
```

`drizzle-kit generate` reads that config and emits `"confirmation_code"`. Correct migration, correct database.

## The bug

**`drizzle.config.ts` is read only by drizzle-kit.** The runtime instance reads its own options:

```ts
drizzle(pool, { schema });                          // ✗ derives "confirmationCode"
drizzle(pool, { schema, casing: 'snake_case' });    // ✓ derives "confirmation_code"
```

With the config-only version, migrations create `confirmation_code` and every query asks for
`"confirmationCode"`. **Every single query fails** with a column-does-not-exist error.

The property-to-column mapping is not written down anywhere in the schema — it is *derived*, and derived
independently by each side. Nothing cross-checks them.

## Why nothing catches it

- `tsc` is happy: the TypeScript types come from the schema object, not from the database.
- ESLint has no opinion.
- Unit tests pass, because tests that touch a database are the ones you do not have yet.
- The production build passes.

A project that names every column explicitly — `text('confirmation_code')` — is immune, which is why one
codebase can carry this pattern safely while its sibling does not. If you copy a `db/index.ts` between
projects, copy the schema's column-naming convention with it or check the `casing` option.

## Pin it with a test that needs no database

Drizzle builds SQL lazily and `pg` does not connect until a query runs, so a connection string that goes
nowhere is enough to inspect the statement:

```ts
const db = drizzle(new Pool({ connectionString: 'postgresql://u:p@127.0.0.1:1/x' }), { schema, casing: 'snake_case' });

it('writes snake_case for a multi-word column', () => {
  const { sql } = db.select().from(schema.bookings)
    .where(eq(schema.bookings.confirmationCode, 'X')).toSQL();
  expect(sql).toContain('confirmation_code');
  expect(sql).not.toContain('confirmationCode');
});
```

Assert the negative as well as the positive — `toContain('confirmation_code')` alone would still pass if the
query somehow contained both.

## The general shape

Any time a mapping is *derived* rather than *declared*, and two tools derive it separately from separate
config, they can disagree silently. Look for the same pattern in ORM naming strategies, serialization
`@JsonNaming`, and code generators that read a config the runtime does not.
