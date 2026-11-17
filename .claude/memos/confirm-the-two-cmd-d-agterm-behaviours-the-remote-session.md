---
created: 2026-11-16 16:10:36
platform: macos
---

# Confirm the two cmd+d agterm behaviours the remote-session README states, once agterm has session split command

The cmd+d paragraph in claude/remote-session/README.md, written by a review fix on 2026-11-15, states two agterm behaviours nobody has observed: with a cmd+d split open, when the main pane stops and a key is pressed in it, agterm moves the split into its place; and cmd+shift+r then takes that tab for the project's attached one. On 2026-11-16 the Mac's installed agterm.app predated `session split command` (`agtermctl session split --help` listed only visibility and close), so attach.sh's split call failed, cmd+d stayed local, and neither behaviour could be tried. Next step, once agterm is rebuilt with the command: open a remote tab, press cmd+d, stop the main pane and press a key in it, then press cmd+shift+r, and correct the paragraph wherever agterm does otherwise. Both need the user at the Mac.
