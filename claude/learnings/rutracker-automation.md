# Automating anything around rutracker.org

Every route a script would take to rutracker is closed except the user's own browser: Cloudflare challenges scripted requests, the JSON API's useful endpoints are switched off, and search and `.torrent` downloads need a login. What survives is the topic page itself, readable anonymously by a real browser or a cloud scraper, and it carries everything a download needs. Measured 2026-10-03/04.

## What a script can and cannot reach

| Route | Result |
|---|---|
| `curl` (any User-Agent) to `viewtopic.php`, `tracker.php`, `dl.php`, even `robots.txt` | 403, Cloudflare managed challenge ("Just a moment…"). `forum/index.php` answered 200 once. Measured through a VPN; a non-VPN address may differ. |
| `api.rutracker.cc/v1/get_tor_topic_data`, `get_tor_hash`, `get_peer_stats`, … | HTTP 200 with `{"error":{"code":1,"text":"Temporarily disabled"}}`. Only `static/*` endpoints answer (`static/pvc/f/<forum>` lists every topic's info-hash, seeders and size, but no title). `api.t-ru.org` does not connect. |
| Firecrawl cloud scrape of a topic page | Works anonymously, 1 credit: title, the release-details block, the MediaInfo spoiler and the magnet link. The file list and seeder counts are absent. |
| Firecrawl to `tracker.php` (search) or `dl.php` | Gets past Cloudflare, then redirects to `login.php`. |
| Self-hosted Firecrawl | Lacks the cloud's anti-bot engine; fails like `curl`. |
| Jackett / Prowlarr RuTracker indexers | Need FlareSolverr since mid-2026; work for some users and time out or lose cookies (IPv4/IPv6 mismatch) for others. |

So automation that needs a release belongs in the user's logged-in browser: an extension or bookmarklet reading the page they already have open.

## The topic page

- **Title**: `h1.maintitle`, or `document.title` minus ` :: RuTracker.org`. Format: `RU / [alt RU /] EN / Сезон: N[-M] / Серии: a-b из c (directors) [years, countries, genres, SOURCE RES] <track summary>`, e.g. `2 x MVO (TVShows, HDRezka Studio) + Original + Sub (Rus, Ukr, Eng)`. A show's bracketed year is the *season's* year, so it matches the first-air year only for season 1. Markers vary: `Сезон: 1`, `Сезон 1`, `Сезон: 1-8`, `Серии 1-6 из 6`, `0-8 из 9`.
- **Magnet**: `a.magnet-link[data-topic_id]` (logged in: a direct child of `div.post_wrap`; logged out: inside `fieldset.attach > div.attach_link.guest`). It carries `xt`, `tr=http://bt.t-ru.org/ann?magnet` and a truncated `dn` — **no passkey, logged in or out** (checked on one topic logged in). The `.torrent` from `dl.php` does carry the user's passkey, which rutracker's rules forbid handing to anyone else (rules topic t=1045, §1).
- **Release details**: a key/value block at the top of the first post (`Качество`, `Видео`, one `Аудио` line per track with its studio, `Субтитры`), then folded spoilers `.sp-wrap > .sp-head` labelled `Список серий`, `MediaInfo` (per-track language, title, default/forced), `Скриншоты`. Folded content is still in the DOM.
- **Ids**: `.post_body[data-ext_link_data]` holds `{"p","t","f","u"}` — post, topic, forum, uploader — so the forum (series vs movies) needs no breadcrumb parsing. An IMDb link in the first post gives `tt…` for matching.
- **Read only the first post**: replies carry their own magnets and IMDb links, and on page 2+ of a topic the first post on the page is a reply. Scope to the post's container, `#topic_main tbody[id^="post_"]`, not to its `.post_body`: the magnet sits beside the body, not inside it.
- **Page number**: the pager renders the current page as a bare `<b>N</b>` among `a.pg` links, inside the same `<b>` that holds `.pg-jump-menu` (`.pg-jump-menu`'s parent, `:scope > b`). A one-page topic has no pager. `start=` in the URL is not enough, since a `?p=<post>` link can land on any page.
- **Unknown or deleted topic**: `viewtopic.php` answers 200 with a notice page — `table.forumline.message` reading "Тема не найдена" — and no `h1.maintitle` or posts, which tells it apart from a layout change.
- **Encoding**: pages are Windows-1251; decode accordingly when fetching one from script.
- **Parsing Cyrillic with JS regex**: `\b` is ASCII-only and never ends a Cyrillic word, so `/^Сезон\b/` fails on "Сезон: 4". Use a lookahead such as `(?=[\s:]|$)`.

## Specials in a release

A topic's episode count includes any special it packs, so `Серии: 1-13 из 13` on a four-season Sherlock pack is twelve episodes plus "The Abominable Bride". Inside the torrent such a special is usually named by its title alone, with no episode number and sometimes a misspelt show name (`Season 4/Sherlok.The Abominable Bride.avi`, beside `Sherlock.s04e01.avi`), and its subtitles follow the same stem (`Sherlok.The Abominable Bride.RUS.FORCED.srt`). Mapping such files onto episodes therefore needs a match against the catalog's episode titles; a number-only parser files the special as unknown and separates it from its subtitles.

The opposite case looks the same from the title and is not a special at all. The Sandman's "A Special Episode - Death: The High Cost of Living" is S02E12 in TMDB (where `episode_type` is `finale`), in TheTVDB and in the release's own file names, so the word "special" in a title says nothing about season 0. Comments on a topic page sometimes quote the torrent's file list, which is the only way to see it without logging in.

## Search page (logged in only)

`tracker.php?nm=<query>&f=<forum ids>`; rows `table#tor-tbl > tbody > tr`, title `a.tLink`, size `td.tor-size[data-ts_text=<bytes>]`, seeders in column 7 (or days since a seeder was seen, containing "дн"), added time `data-ts_text`. Fifty rows per page. Rutracker's global CSS forces `a:hover { color: #dd6900 !important; text-decoration: underline !important }`, so UI injected into the page needs a shadow root.
