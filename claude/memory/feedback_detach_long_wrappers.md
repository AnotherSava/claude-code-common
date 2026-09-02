---
name: Detach a wrapper that spawns a survivor
description: Launch long-running wrappers with nohup + disown rather than as a foreground Bash call, or a later task-kill takes the spawned process group with it
metadata:
  type: feedback
---

Launch a wrapper that spawns something meant to outlive it with `nohup … & disown`, not as a plain foreground Bash call — and never pipe it into `tail`/`head`.

**Why:** `bash scripts/deploy.sh` starts a dev server detached and then lingers rather than exiting. Piping it to `tail` held its stdout open, so the call never returned; it hit the tool timeout, became a harness background task, and stopping that task killed the whole **process group** — taking the dev server down with it. The `nohup … &` inside the script does not survive a group kill. Two things went wrong on top of that: the pipe also swallowed the script's own progress output, so its log file came back empty and I misdiagnosed the hang as the script lingering rather than the pipe holding it; and I had already told the user the server was live, which by then it was not.

**How to apply:** for anything that spawns a survivor, `nohup cmd > /tmp/x.log 2>&1 & disown`, then `sleep` and verify independently — check the socket with `lsof -nP -iTCP:<port> -sTCP:LISTEN -t` or make a real request, rather than trusting the launcher's own words. Read the log file afterwards instead of piping the command. When a foreground call unexpectedly hits its timeout, suspect a held-open stdout before concluding the program hangs. Related: [[feedback_probe_must_not_perturb]], [[feedback_verify_at_the_user_visible_layer]].
