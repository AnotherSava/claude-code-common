# Exercising a Next.js server action without a browser

A form bound to a server action works without JavaScript, and that no-JS path can be driven from `curl`, which is
enough to check what an action does — what it writes and where it redirects — on a machine with no headless
browser installed.

## How

1. Render the page that holds the form, with whatever query string makes the form appear, and read its fields:

   ```bash
   curl -s 'localhost:<port>/inbox?item=<id>' | grep -o 'name="\$ACTION_ID_[^"]*"\|name="ids"[^>]*'
   ```

   Every form bound to an action carries a hidden `$ACTION_ID_<hex>` input; the hex is the action's id. A page
   with two such forms carries two ids, in document order.

2. POST a multipart body to the same page: the `$ACTION_ID_<hex>` field with an empty value, plus the form's own
   fields as the page rendered them.

   ```bash
   curl -s -o /dev/null -D - -X POST 'localhost:<port>/inbox' \
     -F '$ACTION_ID_<hex>=' -F ids=<id> -F other-field=<value> | grep -i '^HTTP\|^location'
   ```

3. An action that ends in `redirect()` answers `303 See Other` with the target in `Location`. One that does not
   redirect answers `200` with the re-rendered page.

## Limits

- It proves the server side only. With JavaScript the client router follows the same redirect through an RSC
  request carrying a `Next-Action` header, and that path is not exercised; say so when reporting.
- The id is resolved against the page it is posted to, so post to the page that rendered the form
  (`nextjs-server-actions-path-gating.md` has why).
- The action really runs: snapshot whatever it writes first and restore it afterwards.
