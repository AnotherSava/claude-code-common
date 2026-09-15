# Fixture: a repo that already names one npm version, and a manifest missing it

`web/package.json` pins npm and the scraper beside the skill that runs it does not. The
value is copied from the manifest that has one rather than resolved fresh, so this repo
does not end up running two npm versions against two lockfiles.
