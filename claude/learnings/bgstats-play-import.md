# Pushing a play into BG Stats from another app or site

BG Stats (the Board Game Stats phone app) documents one way for an outside app or website to hand it a logged
play: a link. Tapping it on a phone with the app installed opens an import dialog, where the game, players and
location are matched to the user's own entries, and the play is saved. The spec is the page "Linking and pushing
to BG Stats from other apps or websites" in the support section of bgstatsapp.com; read 2026-11-06.

```
https://app.bgstatsapp.com/createPlay.html?data=<url-encoded JSON>
bgstats://app.bgstatsapp.com/createPlay.html?data=<url-encoded JSON>
```

## The JSON

```json
{
  "sourceName": "My app",
  "sourcePlayId": "2222427",
  "playDate": "2020-10-23 19:16:58",
  "durationMin": 36,
  "location": "Home",
  "comments": "Such a close play!",
  "board": "",
  "game": { "name": "Roll for the Galaxy", "sourceGameId": "21df231", "bggId": 132531, "highestWins": true, "noPoints": false },
  "players": [
    { "name": "Eerko", "sourcePlayerId": "23432", "startPlayer": true, "winner": true, "score": 47.3, "rank": 1, "role": "", "team": "" }
  ]
}
```

| Field | Required | Notes |
|---|---|---|
| `sourceName` | yes | the sending app; also the location when `location` is absent |
| `sourcePlayId` | yes | the sender's id for this play |
| `playDate` | yes | when the play **ended**, `yyyy-MM-dd HH:mm:ss`; the spec says **UTC**, but the app reads it as local time (see "What the app does with `playDate`") |
| `game.name`, `game.sourceGameId` | yes | `sourceGameId` is what later imports re-match on |
| `players[].name`, `players[].sourcePlayerId` | yes | same re-matching role as `sourceGameId` |
| `durationMin`, `location`, `comments`, `board` | no | keep `comments` short: it rides in the URL |
| `game.bggId`, `highestWins`, `noPoints` | no | `bggId` is recommended; it drives the match suggestion |
| per player `startPlayer`, `winner`, `score`, `rank`, `role`, `team` | no | multiple roles or boards are joined with `／` (U+FF0F), not `/` |

## What the app does with `playDate`

The app files the play under the date written in `playDate` as wall-clock time on the phone, whatever the spec says
about UTC. Observed 2026-11-12 with a phone on Pacific time: a session that ran 18:00–22:00 Pacific was sent, per the
spec, as `"<next day> 06:00:00"` UTC, and the app filed it on the next day. Read as UTC it would have stayed on the
day it was played. The app shows a play's date and not its time, so the time it stored could not be read off the
phone, and that one play is the whole evidence. A sender that wants plays on the right day sends the wall-clock time
of the place they were played.

## Choosing the source ids

The app remembers each match the user makes against the sender's ids, per sender. So `sourceGameId` and
`sourcePlayerId` have to stay the same for the same game and the same person across plays. An id minted per
play — a session's or table's own id — makes the user match the same game and the same friends at every import.
A BGG id, or a normalised title, for the game, and a normalised name for a person, hold still.

## What happens when the link is opened

`app.bgstatsapp.com` publishes an `apple-app-site-association` claiming every path and an Android `assetlinks.json`
for `nl.eerko.boardgamestats`, so a tapped `https://` link opens the app directly. When the phone hands the link to
the browser instead — a universal link reached through a server redirect may not open the app — the page that loads
says so and carries a "CLICK HERE" link, which retries with the `bgstats://` scheme. A redirect through your own
server therefore costs at most one extra tap.

A website cannot detect whether the app is installed; the spec suggests a user setting that shows the button.

## Routes that do not carry a play

- `addPlay.html?gameId=<bggId>&location=<name>` only opens an empty New Play screen with the game and location
  preselected.
- The `.bgsplay` share file and the QR-code share have no published format.

Not stated in the spec: whether re-sending a `sourcePlayId` replaces the earlier play or adds a second one, and
whether a play with an empty `players` array is accepted.
