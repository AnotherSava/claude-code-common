---
created: 2026-09-29 13:22:46
---

# Every other HTML artifact handed over is still machine-local

/github-status now publishes its HTML report on the tailnet, so the one link printed opens on either machine. Every other HTML artifact this fleet produces still goes out as a file:/// path that opens on exactly one machine: the contact sheets feedback_image_report_always mandates, comparison pages, generated reports from other skills. Same problem, already solved once.

What generalizing means: lift publish_report() and serve-report.py out of the github-status skill into a shared script (claude/scripts/ or skills/shared/), taking a file path and returning a URL or None, and call it from wherever an HTML artifact is handed over. The logic worth sharing is the whole platform split - direct path serving on Windows/Linux, a loopback server on macOS because the sandboxed build refuses paths - plus verifying the URL by fetching it before printing, and falling back loudly to file:/// on any failure.

Not done now on purpose: there is one real call site, and CLAUDE.md's Single Source of Logic says to extract at 2-3, not speculatively. The trigger for this memo is the second artifact that wants a cross-machine link, and at that point it is a shared module rather than a copy - the grep that finds both is the extraction trigger, not a worklist.

One design question the second call site settles: the served path is currently hardcoded to /github-status.html and the port to 8787, which one file can assume and a general helper cannot. A shared version needs a path derived from the filename and either a port per artifact or one server holding several files - and a single server serving several files reopens what the single-file design deliberately closed, namely that the state file and description cache sitting beside the report stay unreachable.
