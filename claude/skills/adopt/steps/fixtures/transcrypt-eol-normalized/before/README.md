# Fixture: a repo whose transcrypt rules are not normalized

Both `filter=crypt` rules here are wrong, in the two ways the fleet actually spells them: the first
carries `-text`, which disables normalization outright, and the second names neither `text` nor
`eol`, which leaves the answer to whatever `core.autocrlf` each machine happens to have.

The two `filter=lfs` rules beside them carry `-text` correctly — an LFS object is genuinely binary —
and the step must leave them exactly as they are.

No file matching any of these patterns ships in the fixture, deliberately. The trees here are
committed to a repo that has transcrypt wired, and a nested `.gitattributes` applies there too, so a
`*.secret.*` file inside a fixture would be encrypted into the dotfiles repo's own history and would
read as ciphertext on any clone nobody had unlocked. The rules are the artifact this step reads and
rewrites; the files they would match are not needed to exercise it.
