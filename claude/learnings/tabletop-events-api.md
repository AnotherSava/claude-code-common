# Tabletop.events API

Tabletop.events (TTE) hosts schedules for board game conventions. It exposes a public REST API implementing the
third-party **Wing** protocol (Plain Black Corp). Base URL `https://tabletop.events/api`.

Docs live at `https://tabletop.events/developer/` — hand-written HTML, one page per object. There is **no
OpenAPI/Swagger spec**, no `api.`/`developer.`/`docs.` subdomain, and their own pages link to 404s
(`EventHost.html`, `Friendship.html`). The documented property tables are **incomplete**: `end_date`,
`custom_fields`, `msg_name`, `refundable` and `session_seats` all come back live but are absent from
`EventProperties`. Treat the docs as a starting point, not an authority — several statements in them are
contradicted by the running system (see *Docs that are wrong* below).

## Auth model

| Need | Auth |
|---|---|
| Schedule, seat counts, hosts, attendee names | **None** |
| A user's own badges/tickets, group membership | Session |
| Per-person rosters by ticket, others' user objects | Not obtainable by an ordinary account |

Everything an ingestion adapter needs is anonymous. Verified across two conventions and ~1,160 activities.

**Sessions**: `POST /api/session` with form-encoded `username`, `password`, `api_key_id`. The API key is free
(log in → preferences → "are you a developer" = **Yes** → save → an API Keys link appears → request one). A key
object carries `id` (viewable by *Everyone* — an identifier, not a secret) and a nullable owner-only
`private_key`; only `id` is used by the session endpoint.

- **`username` is not the email address.** Passing an email returns `440 User not found`. The `User` object has
  separate `username` and `email` properties.
- The session id travels as a **`?session_id=` query parameter**, not a header.
- `DELETE /api/session/{id}` revokes it. Do this in a `finally`.
- Regular end users are supposed to use their SingleSignOn interface instead; `Session.html` says "Only
  developers can log in using this interface", which in practice means the account needs the developer
  preference set.

### Status codes

Non-standard and load-bearing — a client that only handles 401/403 misreports them:

- **440** — user not found (bad username)
- **441** — session required. Says nothing about whether you'd be *allowed* once authenticated.
- **450** — insufficient privileges. This is the real refusal.

Distinguishing 441 from 450 is how you tell "needs login" from "will never be allowed".

## The traps

**Datetimes are UTC while looking like local wall-clock time.** `start_date` / `end_date` are naive
`YYYY-MM-DD HH:MM:SS` with no `Z` and no offset — and they are always UTC. Parsing them in the venue's timezone
shifts an entire convention by its offset. Confirmed three ways: `end_date − start_date == duration` minutes on
every sampled row; an event with `start_date 2026-08-29 15:00:00` carries `startdaypart_name "Saturday at
9:00 AM"` for a Denver venue (UTC−6 in August); and their own CSV export names the column "Start Date (UTC)".

**`_items_per_page` caps at 100 and silently reverts to 25.** Ask for 200, get 25. Always read
`result.paging.total_pages` rather than computing page counts. Related quirk: when the page size is *honoured*
the echoed `items_per_page` is a **string**; when reverted it is an **integer**. Coerce before comparing.

**Unknown query parameters are silently ignored, not rejected.** `?uri_part=tacticon` returns all 2,000+
conventions. `_sort_by` is ignored on `/api/convention`. Date and derived-field qualifiers
(`date_updated=>…`, `available_quantity=>0`) are ignored. So a filter that appears to work may be doing
nothing — validate every new filter against a known-mixed dataset before trusting it. Corollary that bites
hard: **an absent key never proves a permission gate**, because a bogus `_include` also adds no key.

**Some `_include` values mutate existing data.** `_include=end_date` rewrites `end_date` to
`start + duration − eventtype.end_buffer`, silently shortening every activity by ~10 minutes.
`_include=host_badge_numbers` adds a field inside the existing `hosts[]` objects. Others
(`attendees`, `hosts`, `multi_spaces`, `eventgroups`) are inert. **Diff before/after whenever the include set
changes** — don't assume.

## Seats and availability

There is no sold-out boolean and no "limited" state. Derive from counters, in this order — each step exists
because of an observed case:

1. **`is_cancelled == 1` → cancelled.** Must come first: cancelled events keep `sellable: 1` **and a full
   `available_quantity`**, so seat arithmetic alone reports them wide open.
2. **`max_quantity == 0` → unticketed drop-in.** These return the sentinel `available_quantity: 1`. Reporting
   "1 seat left" for a no-signup-needed activity is the most misleading thing an adapter can do. `taken_count`
   on these can still be in the dozens — the sentinel does not imply zero attendance.
3. **`available_quantity == 0` and `wait_count > 0` → waitlist**, else **sold out**.
4. Otherwise open.

**Read `available_quantity`; never recompute it** as `max_quantity − taken_count`. Host seats and a
per-convention/per-eventtype `limit_ticket_availability` fraction reduce it invisibly, and roughly 1 row in 400
matches neither that formula nor `unreserved_quantity − taken_count` with all the documented explanations ruled
out.

**`wait_count > 0` does not mean sold out.** Events with seats remaining routinely have someone waiting.
Treating a waiter as sold-out makes the state flap on every ticket sale.

Cancelled events stay in the result set (`is_cancelled=1` is a queryable filter) — disappearance is never a
cancellation signal.

## Structure

`GET /api/convention/{id}/events` returns **one row per event**, carrying only the **first sitting's**
`start_date`/`end_date`/room. Additional sittings live in `GET /api/convention/{id}/eventsessions`, keyed by
`event_id`, and carry **no seat counters** — seats are pooled at the event level, one ticket covering every
sitting. An adapter reading only `/events` silently drops real calendar occurrences.

Useful identity notes:

- Event `id` is a 36-char GUID the docs promise never changes. Despite the docs calling ids case-sensitive,
  **lowercased convention ids work** and return the identical result set.
- `view_uri` is a site-relative path ending in the per-convention `event_number`, not the GUID — it can only be
  used, not constructed.
- The cross-convention `GET /api/event` is admin-only (441). Search events through a parent: convention,
  DayPart, EventGroup, EventType, Room or Space.
- `space_name: "multiple spaces"` is a sentinel; the real list needs `_include=multi_spaces`.
- Event types are per-convention, organizer-authored free text. So is `age_range` — documented as an enum
  (`all|kids|preteen|teen|adult|drinking_age`) but one convention returns `Teen Friendly`, `Kid Friendly`.

## Rate limits and caching

Their docs ask for **no more than 1 request/second**; the stated penalty for abuse is a block, not a 429.
There are **no rate-limit headers**, **no ETag/Last-Modified** and no `Cache-Control`, so conditional GET is
impossible and every poll is a full sweep. Self-impose a delay and go sequential.

Cost per poll ≈ `2 + ceil(events/100) + ceil(sessions/100)`. A 355-event convention is ~7 requests (~20 s);
a 9,000-event one is ~90 requests and several minutes.

**Always reconcile a paged sweep against `paging.total_items`.** A short sweep that goes unnoticed is
catastrophic for anything that diffs against stored state — it reads as "everything vanished".

## Reading a user's own sign-ups

The documented route is **broken**: `GET /user/{id}/event_reservations` returns HTTP 500 with a Perl stack
trace (`Can't locate object method "add_warning" via package "TTE::DB::ResultSet::EventReservation"`).

Working route, with a session:

1. `GET /user/{me}/badges` → one badge per convention the user is registered for
2. `GET /convention/{conventionId}/tickets?badge_id={badge.id}` → their tickets, each naming an `event_id`

Verify the `badge_id` filter actually applied — see the silently-ignored-parameter trap. Filtered vs unfiltered
counts on the same convention is the check (e.g. 5 vs 1,576).

Ticket rows contain `event_id`, `badge_id`, `ticket_number` — **no name and no user_id**. Reading another
user's badge is 450, so a ticket cannot be traced to a person this way.

## Privacy-relevant surfaces

Worth knowing before ingesting any of it:

- **Attendee names are public.** `GET /api/event/{id}?_include=attendees` returns
  `{name, is_reservee, ticket_number, champion, is_host, in_cart}` **anonymously**, and the roster is complete
  (attendee row count equals summed `taken_count`). It's an include on a call you already make, so it costs no
  extra requests. Gated per convention by an organizer-set `event_attendees_visible` flag — roughly a quarter
  of upcoming scheduled events are hidden. That flag is an **organizer** setting, not attendee consent.
- **Host names are frequently raw email addresses** (~6–8% of host values across two conventions).
- **`avatar_uri` is `md5(account_email)`**, case-preserved (not lowercased, contrary to Gravatar's spec),
  served anonymously wherever users appear. That makes it an email-confirmation oracle — and, usefully, a
  login-free way for a user to identify their own account from a list you already hold.
- **Any authenticated user can list any convention's full ticket set** (thousands of rows), despite
  `Ticket.html` stating the registration `ConventionPrivilege` is required. Rows are pseudonymous but cluster
  by `badge_id` into per-attendee schedules.

## Docs that are wrong

Verified against the running system:

- Ticket access does **not** require `ConventionPrivilege` for listing (only per-badge reads do).
- Convention ids are **not** case-sensitive in practice.
- `EventProperties` omits fields the API returns.
- `GET /user/{id}/event_reservations` is documented but 500s.
- `_include=multi_spaces` is **absent** on ordinary rows, not null.

Escalation address in their docs is `info@tabletop.events`; they state plainly that they provide no technical
support for API access and reserve the right to change it without notice.
