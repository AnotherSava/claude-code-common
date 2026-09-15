# Fixture: a declared range with nothing enforcing it

`engines.node` is declared and there is no `.npmrc` anywhere, so npm warns about a wrong
runtime and installs anyway. v8 creates the file beside the manifest.
