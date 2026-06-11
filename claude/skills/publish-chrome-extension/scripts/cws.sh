#!/bin/bash
# Chrome Web Store API helper — republish a new version of an existing extension.
#
# Subcommands:
#   init <client_id> <client_secret>   save OAuth client credentials to config/cws.conf
#   auth                               print the authorization URL (user opens it, copies the code)
#   exchange <code>                    trade the authorization code for a refresh token (saved to config)
#   upload <item_id> <zip>             upload a new package zip to the existing store item
#   publish <item_id>                  submit the uploaded draft for Web Store review
#   status <item_id>                   show the item's draft state
#
# Responses are printed as raw JSON for the caller to inspect (uploadState, status, itemError).
set -euo pipefail

CONF="$HOME/.claude/skills/publish-chrome-extension/config/cws.conf"
REDIRECT_URI="http://localhost:8818"
SCOPE="https://www.googleapis.com/auth/chromewebstore"

usage() {
  echo "usage: cws.sh init <client_id> <client_secret> | auth | exchange <code> | upload <item_id> <zip> | publish <item_id> | status <item_id>" >&2
  exit 1
}

# Extract a top-level string field from a JSON response on stdin.
json_field() {
  sed -n 's/.*"'"$1"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1
}

load_conf() {
  [ -f "$CONF" ] || { echo "Missing $CONF — run: cws.sh init <client_id> <client_secret>" >&2; exit 1; }
  . "$CONF"
}

access_token() {
  load_conf
  [ -n "${REFRESH_TOKEN:-}" ] || { echo "No REFRESH_TOKEN in $CONF — run: cws.sh auth, then cws.sh exchange <code>" >&2; exit 1; }
  local token
  token=$(curl -s -d client_id="$CLIENT_ID" -d client_secret="$CLIENT_SECRET" -d refresh_token="$REFRESH_TOKEN" -d grant_type=refresh_token https://oauth2.googleapis.com/token | json_field access_token)
  [ -n "$token" ] || { echo "Failed to obtain an access token — the refresh token may be expired or revoked. Re-run: cws.sh auth, then cws.sh exchange <code>" >&2; exit 1; }
  echo "$token"
}

case "${1:-}" in
  init)
    [ $# -eq 3 ] || usage
    mkdir -p "$(dirname "$CONF")"
    printf 'CLIENT_ID=%s\nCLIENT_SECRET=%s\n' "$2" "$3" > "$CONF"
    echo "Saved client credentials to $CONF. Next: cws.sh auth"
    ;;
  auth)
    load_conf
    echo "Open this URL in a browser logged into the Chrome Web Store publisher account, approve access,"
    echo "then copy the 'code' query parameter from the localhost URL you land on (the page itself fails"
    echo "to load — that's expected). URL-decode it if it contains %2F (replace with /)."
    echo
    echo "https://accounts.google.com/o/oauth2/auth?response_type=code&scope=$SCOPE&access_type=offline&prompt=consent&client_id=$CLIENT_ID&redirect_uri=$REDIRECT_URI"
    echo
    echo "Then run: cws.sh exchange <code>"
    ;;
  exchange)
    [ $# -eq 2 ] || usage
    load_conf
    refresh=$(curl -s -d client_id="$CLIENT_ID" -d client_secret="$CLIENT_SECRET" -d code="$2" -d grant_type=authorization_code -d redirect_uri="$REDIRECT_URI" https://oauth2.googleapis.com/token | json_field refresh_token)
    [ -n "$refresh" ] || { echo "Token exchange failed — authorization codes expire within minutes. Re-run: cws.sh auth" >&2; exit 1; }
    printf 'REFRESH_TOKEN=%s\n' "$refresh" >> "$CONF"
    echo "Refresh token saved to $CONF. Setup complete."
    ;;
  upload)
    [ $# -eq 3 ] || usage
    [ -f "$3" ] || { echo "Zip not found: $3" >&2; exit 1; }
    token=$(access_token)
    curl -s -X PUT -H "Authorization: Bearer $token" -H "x-goog-api-version: 2" -T "$3" "https://www.googleapis.com/upload/chromewebstore/v1.1/items/$2"
    echo
    ;;
  publish)
    [ $# -eq 2 ] || usage
    token=$(access_token)
    curl -s -X POST -H "Authorization: Bearer $token" -H "x-goog-api-version: 2" -H "Content-Length: 0" "https://www.googleapis.com/chromewebstore/v1.1/items/$2/publish"
    echo
    ;;
  status)
    [ $# -eq 2 ] || usage
    token=$(access_token)
    curl -s -H "Authorization: Bearer $token" -H "x-goog-api-version: 2" "https://www.googleapis.com/chromewebstore/v1.1/items/$2?projection=DRAFT"
    echo
    ;;
  *)
    usage
    ;;
esac
