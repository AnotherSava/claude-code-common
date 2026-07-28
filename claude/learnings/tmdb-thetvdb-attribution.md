# TMDB + TheTVDB API attribution requirements (verified July 2026)

How to legally attribute these two metadata APIs. Both are free for non-commercial / small-scale use **with** attribution. Verified against the official terms pages.

## TMDB (The Movie Database)

Sources: https://developer.themoviedb.org/docs/faq · logos: https://www.themoviedb.org/about/logos-attribution

- **Notice is MANDATORY, verbatim:** `This product uses the TMDB API but is not endorsed or certified by TMDB.`
- **Logo is REQUIRED** — text alone is not enough. Use one of their **approved** logos, unmodified (no recolor/rotate/flip beyond the approved variants), and **less prominent** than your app's own branding.
- **Placement:** the attribution must be within an **"About" or "Credits"** section — NOT required on every page.
- **Link** the logo to `https://www.themoviedb.org`.
- **Naming** (in prose): refer to them only as **"TMDb"** or **"The Movie Database"**.
- **Logo asset URLs** — scrape the logos-attribution page for the current hashed filenames (they rotate). Pattern:
  `https://www.themoviedb.org/assets/2/v4/logos/v2/blue_long_1-<hash>.svg` — primary horizontal wordmark, gradient, works on light **or** dark. Also `blue_long_2`, `blue_short`, `blue_square_1`, `blue_square_2`.
- Free for non-commercial with attribution; contact them for commercial licensing.

### Image hotlinking, caching & usage limits (verified July 2026)

Sources: TMDB API Terms of Use (https://www.themoviedb.org/api-terms-of-use) + TMDB staff forum posts.

- **Hotlinking `image.tmdb.org` is explicitly allowed.** Build `https://image.tmdb.org/t/p/{size}{file_path}` (e.g. `w342`, `w500`, `original`) and use it directly from the browser (still attribute TMDB). This is the documented, supported pattern — not a hack; staff: *"Yes, no problems. Just remember to properly attribute."*
- **The image CDN is NOT rate-limited** — staff: *"this service is not rate limited like the api is."* Unlike the JSON API (which is), per-viewer hotlinking of posters/backdrops/profile photos won't get throttled. So storing only the *path* and hotlinking at view time is a legitimate architecture (no local image cache required).
- **Caching is encouraged but capped:** don't cache TMDB data (metadata or images) for **longer than 6 months**; you acknowledge you don't own the data and must **purge it on request or on license termination**.
- **Commercial use needs a separate commercial API key** (a written agreement) — the free key is non-commercial only.
- **Training ML/AI on TMDB content is prohibited** (LLMs/chatbots, collecting datasets of TMDB content, or redistributing cached datasets for training).
- **Bandwidth abuse is barred** (don't degrade their servers) — normal app hotlinking is nowhere near this threshold.

## TheTVDB

Source: https://www.thetvdb.com/api-information

- **Mandatory (verbatim):** `attribution with a direct link to TheTVDB.com must be displayed to end users viewing metadata from our API.` (Command-line tools / dev libraries may show it on an about/readme page instead.)
- **No specific wording is required.** Their `Metadata provided by TheTVDB. Please consider adding missing information or subscribing.` sits under a heading literally labeled **"Sample Attribution"** — it's an example, not a mandate. The "subscribing" nudge matters mainly under the user-supported key model.
- **A linked logo alone suffices** — no visible sentence needed — as long as it carries the credit:
  ```html
  <a href="https://www.thetvdb.com"><img alt="Metadata provided by TheTVDB" title="Metadata provided by TheTVDB" src="..."></a>
  ```
  The `alt`/`title` is the textual credit (what screen readers announce, and what satisfies any "must be text" reading); the `href` is the mandatory direct link. Keep `alt` **meaningful** (name TheTVDB) — not empty/decorative.
- **Logo assets:** `https://www.thetvdb.com/images/attribution/logo1.png` (white "tvdb" — for **dark** backgrounds) and `logo2.png` (dark "tvdb" — for **light** backgrounds). ~400×216 PNG.
- **Pricing tiers** (by company revenue): free < $50k (attribution required), $1k/$10k/custom above. Two key models: a negotiated **licensed** key, or **user-supported** (each end user pays ~$12/yr for a PIN used with your app's key).

## Placement pattern that worked (whats-next)

- **TMDB** → a dedicated `/credits` page (satisfies the About/Credits requirement) with the notice + approved logo, reachable from a footer link.
- **TheTVDB** → the site **footer** — a linked logo shown on every page. Over-attribution is fine and far simpler than per-page scoping to only pages that render TVDB-sourced items.
