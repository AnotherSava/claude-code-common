# Converting an old price: a keyless source of historical exchange rates

Showing what a 2015 purchase cost in today's home currency needs a rate for the day it was made, not for
today — over a decade the difference is not a rounding error, it is the whole number. The obstacle is usually
assumed to be an API key and a bill; it is not, and the real obstacles are two gaps in coverage that a design
has to answer for before it is built.

Measured 2026-10-12.

## The source

```
https://api.frankfurter.dev/v1/<YYYY-MM-DD>?base=<FROM>&symbols=<TO>
→ {"amount":1.0,"base":"RUB","date":"2015-02-20","rates":{"CAD":0.02005}}
```

European Central Bank reference rates, free, no key, no registration, daily history back to 1999.

**Use the `.dev` host.** `api.frankfurter.app` answers `301` through Cloudflare, and a client that does not
follow redirects gets an HTML error page where it expected JSON — which looks like the API being broken
rather than like a moved host.

`date` in the response is the day actually used: ask for a weekend or a holiday and it answers with the
preceding publication day, which is the correct behaviour and worth echoing wherever the rate is explained.

## The two gaps, and why they must be designed for

ECB publishes about thirty currencies, which is not all of them, and it has stopped publishing at least one:

- **RUB ends at 2022-03-01.** That date resolves; `2022-03-02` answers `{"message":"not found"}`. The ECB
  suspended the rouble reference rate at the invasion. Anything after that is simply absent, and no amount of
  retrying changes it.
- **Currencies it never carried** answer the same way at every date. A Jordanian dinar price has no rate here
  at all.

So the design question is not "where do I get rates" but **what the screen says for a price it cannot
convert**. Showing the original alone with the reason is honest; showing a converted figure from a nearby
date, or from today, is the failure this whole exercise exists to avoid — a number that looks computed and
is not what was paid.

Count the affected rows before choosing: in the case measured, 174 of 176 priced records were convertible,
which made "show the original and say why" obviously right. A set where a third is unconvertible would
argue for a different source instead.

## Shape worth building

- **Cache each day's rates in your own store**, fetched once — one EUR-based row per day serves every pair
  (see *Fetching a range, and storing it EUR-based*). A rate for a past day never changes, so there is no
  invalidation problem and no reason to call the API twice for the same day.
- **Never fetch at render time.** The page that shows a price is the one place a network round trip is most
  visible and least recoverable.
- **Convert for display only; keep the original amount and currency as the stored truth.** The converted
  figure is a view of it, and storing one back makes the record depend on the day it was computed.

## Fetching a range, and storing it EUR-based

`GET /v1/<from>..<to>?base=EUR` returns every publication day in the range with all ~30 currencies — daily,
not sampled, measured over a whole calendar year (257 days, ~105 KB). `start_date` moves back to the
publication before `from` when `from` is a weekend or holiday, so the first asked day always has an answer.
One request per calendar year asked about fills a decade of bookings in a dozen calls.

Store each day's rates against EUR rather than against a home currency. ECB publishes against EUR and
frankfurter derives every other pair from it, so a stored EUR row makes any pair a division
(`amount / rate[from] * rate[to]`): changing the home currency fetches nothing and leaves nothing stale.

**Store a day only once its rate is final.** The rate for day D appears on D's afternoon CET. Asked earlier, the
API answers with D−1's — right as "the latest rate", but stored under D for good it makes the same booking
convert differently depending on the hour it was imported. Write a calendar day only when it is before today
or when the answer's own date is that day; a price whose day is not final shows unconverted until the next
fill. A count of "missing" days has to apply the same test, or it raises a warning whose fetch button can
never clear it — all day on a weekend.

## Alternatives, and when they are worth it

A paid provider (openexchangerates, exchangerate.host's paid tier, a central bank's own API per currency)
buys the currencies ECB drops and little else for this kind of use. Reach for one when the gap analysis
above shows a material share of rows unconvertible — not before, and never for the convenience of avoiding a
cache you would want anyway.
