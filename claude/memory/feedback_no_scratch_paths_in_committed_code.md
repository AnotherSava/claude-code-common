---
name: feedback-no-scratch-paths-in-committed-code
description: Committed code and docs must not reference gitignored scratch paths (tmp/, scratch/) — the files get cleaned up and the references rot
metadata:
  type: feedback
---

Docstrings, comments, README, and other committed text must not reference gitignored scratch paths (`tmp/`, `scratch/`, etc.). Either move the referenced file into a canonical in-repo location (e.g. `tests/data/`, `assets/`), or replace the path with a generic description.

**Why:** Scratch directories are local-only and get cleaned up as part of normal hygiene. References to deleted files rot — future readers can't tell whether the code depends on missing data, whether the reference is just historical, or whether they need to recreate something. Real example from `iris.py`: docstrings referenced `tmp/diaframma/obj_7_Diaf 2.stl` as the source mesh for reverse-engineering. When the scratch directory was cleaned, the references became dangling — the code still worked but the documentation pointed nowhere.

**How to apply:**
- Before committing, grep changed text for gitignored roots: `tmp/`, `scratch/`, anything in `.gitignore` that's a directory name.
- Two fixes:
  - **(a) Promote the file**: copy or move it to a canonical in-repo location (e.g. `tests/<feature>/data/`, `docs/<topic>/`) so the reference stays valid. Use this when the file is genuinely needed by tests or as reference data.
  - **(b) Rewrite the prose**: replace the path with a generic description ("the source-mesh reconstruction", "the reference STL", "earlier benchmark output"). Use this when the path was just provenance — readers don't need to find the file.
- Related but distinct from [[feedback-research-to-production-cleanup]]: that one is about deleting research *code* whose lesson lives in docs. This one is about removing *path references* that leak into production text.
- Already-saved global rule: "Never use absolute paths in committed documentation" covers `D:\projects\...` paths. This rule extends it to *relative paths into gitignored scratch* — same failure mode, different surface.
