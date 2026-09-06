# Attaching files to a GitHub issue — what is actually documented

Verified against docs.github.com "Attaching files" (checked 2026-09-03). These matter when writing
product copy or a support workflow that tells a user to attach something, because two of them are the
opposite of what people assume.

## The upload happens on drop, not on submit

> "When you attach a file, it is uploaded immediately to GitHub and the text field is updated to show
> the anonymized URL for the file."

So dragging a file into the comment box **has already published it**, whether or not the comment is
ever posted. Cancelling the comment does not unpublish anything. This is the single most useful thing
to tell a user before they attach a diagnostic bundle: it is why "review it first" is advice with a
deadline rather than a tidiness suggestion.

## On a public repository the file needs no account to read

> "For public repositories, uploaded files can be accessed without authentication."

The URL is "anonymized" in the sense of being unguessable, not access-controlled.

## Deletion is NOT documented

GitHub's docs say nothing about removing an attachment after upload. Community threads claim only
Support can, and that may well be true — but it is not documented, so do not state it as fact in
shipped copy or user-facing docs. Say what is documented and stop.

## Limits and types

- Non-media files: **25 MB**, regardless of plan.
- `.json`, `.log`, `.txt`, `.md`, `.zip` are all accepted, so a JSON diagnostic bundle needs no
  renaming and no zip wrapper.
- There is **no REST or GraphQL endpoint** for issue attachments — upload is browser-only.
  `gh issue comment --attach` does not cover it (media-only, and it needs push access, which a
  reporter does not have). An app therefore cannot upload on the user's behalf; it can only write a
  file and let them attach it.
- An issue comment body caps at **65,536 characters**, so a prefilled `?body=` URL cannot carry a
  payload of any size (and an over-long URL returns HTTP 414).
