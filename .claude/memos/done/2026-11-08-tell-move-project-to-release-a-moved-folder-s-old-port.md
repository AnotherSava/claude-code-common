---
created: 2026-10-21 04:34:42
---

# Tell move-project to release a moved folder's old port claims

deploy-dev-server.sh (claude/skills/deploy/scripts) names its ports-registry use case after the folder: <folder>-dev-server and <folder>-dev-tailnet. The owner is the GitHub repo name since f08043f, but the use-case slug is not, so after a folder move the next deploy allocates fresh claims and the old ones stay in claude/skills/ports/registry.json, owned by the same repo and never released. Next step: add a line to claude/skills/move-project/SKILL.md step 4 telling the user to run 'ports.py release' on the old use cases after the move (or have deploy-dev-server.sh derive the slug from 'ports.py repo-name' instead, which would make a move need nothing). Raised by a review-auto docs-relevance pass on 2026-10-20; the trips session, which wrote the owner change, left it to this repo.
