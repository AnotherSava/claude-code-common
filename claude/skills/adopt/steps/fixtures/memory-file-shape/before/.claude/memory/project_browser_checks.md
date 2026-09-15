---
name: project-browser-checks
description: Drive the headless profile under tmp/, never the user's own Chrome, and kill the whole process tree afterwards
metadata:
  type: project
---

The checks launch their own headless profile under `tmp/profile` and match the processes
to kill on that directory, never on the parent pid. A renderer and a GPU child outlive
the parent and keep writing to the terminal minutes after the run reports done.
