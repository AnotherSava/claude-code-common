# System.Uri rewrites the text you hand it: slice the original string to keep parts verbatim

`Uri.TryCreate` accepts a URL containing characters RFC 3986 does not allow unescaped, and its component
properties return them percent-encoded. A tool that rebuilds a URL from `uri.AbsolutePath`, `uri.Query` and
`uri.Fragment` therefore changes parts it never meant to touch.

Measured on .NET 10 (2026-11-08), rebuilding `https://example.com/{{slug}}/a|b?q={{term}}#{{anchor}}`:

| Input character | What `AbsolutePath` / `Query` / `Fragment` return |
| --- | --- |
| `{` `}` | `%7B` `%7D` |
| `\|` | `%7C` |
| `%20` | `%20`, unchanged |
| `+` | `+`, unchanged |

So a URL cleaner that strips `utm_source` from `https://example.com/?q={{term}}&utm_source=news` hands back
`?q=%7B%7Bterm%7D%7D`, a different URL from the one the user copied.

## The fix

Use `Uri` only to validate the string and read the scheme and host. Take the path, query and fragment as
substrings of the original text: the authority ends at the first `/`, `?` or `#` after `://`; the fragment starts
at the first `#` after that; the query starts at the first `?` before the fragment. Everything not deliberately
removed then comes back byte for byte.

Slicing keeps what the user typed, so dot segments (`/a/../b`) and backslashes stay as typed where `Uri` would
have normalised them. For a tool whose job is to change only what it strips, that is the right trade.
