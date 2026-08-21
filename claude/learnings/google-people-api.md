# Google People API — contacts, labels, and "Other contacts"

How to read a Google account's contacts and their labels programmatically. Auth setup is a separate
topic — see `google-oauth-desktop-app.md`.

Endpoint root is `https://people.googleapis.com/v1`. Scopes: `contacts.readonly` for the contact list,
`contacts.other.readonly` for the "Other contacts" bucket. Both are *sensitive* scopes.

## Labels are contact groups, and only the API tells you which are real

`contactGroups.list` returns every group with a `groupType` of `USER_CONTACT_GROUP` or
`SYSTEM_CONTACT_GROUP`. That flag is the whole reason to prefer the API over the web UI's CSV export:
the CSV has a `Labels` column that joins groups with ` ::: ` and renders system groups with a `*`
prefix (`* myContacts`, `* starred`), but that prefix is a display convention, not a type field. Any
"which contacts have no label" query built on the CSV is guessing that `*` means system.

Every contact belongs to at least one group — `myContacts` — so "unlabeled" can never mean "no
memberships at all". It means *no membership in a group whose `groupType` is `USER_CONTACT_GROUP`*.

A user label with zero members still appears in `contactGroups.list` (with `memberCount: 0`) while
appearing on no contact, so build the distribution from the group list and fill counts in from the
connections, or an empty label silently vanishes from the report.

## `formattedName` is not a maskable field

This one costs a request to discover. `groupFields` rejects it:

```
400  Invalid groupFields mask path: "formatted_name".
```

Note the error echoes the path in snake_case even though the request used camelCase. Valid mask:

```
groupFields=name,groupType,memberCount
```

`formattedName` is output-only, and the distinction matters: it is rejected as a *request* path but the
server **returns it anyway**. So the field is there to read — a `formattedName or name` fallback is live
code, not a dead branch — you just cannot ask for it. It holds the locale-translated display name for
*system* groups; for user groups `name` is what the user typed, which is what you want to display.

## Memberships on a person

Request `memberships` in `personFields` on `people.connections.list`. Each entry is one of:

```json
{"contactGroupMembership": {"contactGroupId": "1a2b", "contactGroupResourceName": "contactGroups/1a2b"}}
{"domainMembership": {"inViewerDomain": true}}
```

Ignore `domainMembership` — that's a Workspace directory contact, not a label. Treat
`contactGroupResourceName` as possibly absent and fall back to building it from `contactGroupId`.

Match memberships against the *known* user-group resource names rather than assuming any unrecognised
group is a label; a membership in a group missing from `contactGroups.list` would otherwise mask a
genuinely unlabeled contact.

Other `people.connections.list` details: `resourceName` must be the literal `people/me`, `pageSize`
maxes at 1000 (default 100), and `sortOrder` accepts `FIRST_NAME_ASCENDING` / `LAST_NAME_ASCENDING` /
`LAST_MODIFIED_ASCENDING|DESCENDING`.

## "Other contacts" are a separate bucket, not unlabeled contacts

`otherContacts.list` reads the addresses Google auto-collects when you mail someone who isn't in your
contacts. They exist to feed Gmail's autocomplete. The API defines them as *contacts in no contact
group*, so they can never appear in a label query — treating them as "contacts with no label" is a
category error, not a finding.

Two differences from `connections.list` worth remembering:

- The parameter is **`readMask`**, not `personFields`.
- Only `names`, `emailAddresses` and `phoneNumbers` are available. That is a server-side restriction;
  asking for more is rejected rather than silently dropped.

The web UI cannot export them at all — its export dialog offers *Selected contacts*, *Contacts*,
*Favorites* and each label, with no scope covering this bucket. The API is the only way to enumerate
them. Expect the count to be far larger than the real contact list, and mostly long-tail: one-off
correspondents, vendors and role addresses (`no-reply@`, `orders@`).

To stop them accumulating, the user turns off Gmail → Settings → General → "Create contacts for
auto-complete". Clearing the existing ones is a bulk delete in the Contacts UI; it needs the
read-write `contacts` scope, so a read-only tool structurally cannot do it.

## The web UI's internal route, and why not to build on it

The Contacts UI generates its CSV export server-side and returns it **inside a `batchexecute` RPC
response**, not as a file download. So the export can be read without ever writing a file: hook
`XMLHttpRequest`/`fetch`, click Export through the real UI, and the CSV arrives as a JSON-escaped
string nested a couple of `JSON.parse` levels deep in the response body.

That works with zero credential setup and is a reasonable one-off. It is a bad foundation for anything
committed: the route is keyed on an opaque rpc id that Google renames at will, the response carries no
`groupType`, and it cannot see Other contacts. Reach for it to answer a question once, then build on
the People API.

## Dead ends

**CardDAV** still exists (`developers.google.com/people/carddav`) but has required OAuth 2.0 since
Google ended basic-auth access for CalDAV/CardDAV/IMAP in March 2025. App passwords are not a
documented path for it. So it costs the same OAuth setup as the People API and hands back vCards
instead of structured JSON — no reason to prefer it.

**Service accounts** cannot read a consumer Google account's contacts. Domain-wide delegation needs a
Workspace admin, so for a personal `@gmail.com` account the installed-app OAuth flow is the only route.
