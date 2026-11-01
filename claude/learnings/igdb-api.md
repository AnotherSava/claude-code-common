# IGDB API — Twitch credentials, store-id matching, and keeping DLC out of search

IGDB is the games catalog Twitch runs. These notes come from building a game search and a Playnite import against it in 2026-10.

## Credentials

IGDB authenticates through a Twitch developer application: register one at `dev.twitch.tv/console/apps` with **Client Type: Confidential** (a public client gets no secret). The form requires an **OAuth Redirect URL, which this flow never uses — `http://localhost` is fine**. Then:

```
POST https://id.twitch.tv/oauth2/token?client_id=…&client_secret=…&grant_type=client_credentials
```

returns an app token valid for about two months (`expires_in` ≈ 5,300,000 s). Cache it and fetch a new one on expiry or on a 401. Requests are `POST https://api.igdb.com/v4/<endpoint>` with headers `Client-ID` and `Authorization: Bearer <token>`, and an Apicalypse body (`fields …; where …; limit …;`). Limits: 4 requests a second, 8 open at once.

## Store ids → games

`external_games` maps a store's own id to an IGDB game:

```
fields game; where external_game_source = 1 & uid = "1003400"; limit 5;
```

`category` is deprecated in favour of `external_game_source`. Source ids, read from `/v4/external_game_sources`: Steam 1, GOG 5, Amazon 20, Amazon ADG 23, Epic Games Store 26, Xbox Marketplace 31, PlayStation Store US 36, Itch.io 30. **Battle.net is not a source**, so its games can only match by name. A uid can map to more than one game; disambiguate by name.

## Search is flooded by DLC and updates — filter on `game_type`

`search "Genshin Impact";` returned ten event updates and no base game; the same happened for other live-service games. Restricting to standalone types fixed it:

```
search "Genshin Impact"; where game_type = (0,4,8,9,10,11); fields …; limit 10;
```

`game_type`: 0 main game, 1 DLC, 2 expansion, 3 bundle, 4 standalone expansion, 5 mod, 6 episode, 7 season, 8 remake, 9 remaster, 10 expanded game, 11 port, 12 fork, 13 pack, 14 update.

## Matching names

- Roman numerals differ from store names ("Baldur's Gate 3" vs "Baldur's Gate III", "Ghostrunner 2" vs "Ghostrunner II"): normalise II–X to digits on both sides before comparing.
- Same name, different games (a 2010 original and a 2023 port, a 1995 and a 2020 "Hades"): break the tie with the release year and treat a remaining tie as unmatched rather than picking one.
- Editions: try the full name first, because IGDB lists some editions ("… Deluxe Edition", "… Nintendo Switch 2 Edition") as games of their own; strip the edition suffix only when the full name finds nothing.
- IGDB renames: "Overwatch 2" is filed as "Overwatch".

Useful game fields: `name, first_release_date` (unix seconds), `summary, cover.image_id, genres.name, platforms.name, involved_companies.developer, involved_companies.company.name`. Cover URL: `https://images.igdb.com/igdb/image/upload/t_cover_big/<image_id>.jpg`.
