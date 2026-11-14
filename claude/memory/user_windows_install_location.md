---
name: user-windows-install-location
description: On the Windows desktop the user keeps a folder of their own for apps, C:\Programs\<App>; install there whenever the installer lets the location be chosen
metadata:
  type: user
---

On the Windows desktop the user keeps a folder of their own for installed apps, `C:\Programs\<App>`. It holds their own tools and third-party apps alike. Software whose installer chose `Program Files` stays there; this folder is where an app goes when the location is open to choose.

On 2026-11-13 they asked for ClipCascade to be moved there from the MSI's default `C:\ClipCascade` right after it was installed, and then chose `C:\Programs\ClipCascade-server` for its self-hosted server over a folder inside a repo. Reading those two choices as a rule for every new install is an interpretation, which the user approved saving that day.

**How to apply:** when installing an app on that machine, pass the installer's directory property, for example `APPDIR=C:\Programs\<App>\` for a WiX MSI (mechanics in the learning `windows-uac-elevation-from-agent-shell.md`). Don't accept the default and move it afterwards. If the installer can't take a target directory, ask before installing.
