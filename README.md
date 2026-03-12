# Claude Code Skills

A collection of reusable [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills for implementation planning, PR workflows, and architecture documentation.

## Skills

---

### Plan Implementation

Interactive design discussion that produces a structured plan document before any code is written.

**Command:** `/plan-ralphex`

**Features:**
- Researches the codebase to understand current architecture and patterns
- Asks clarifying questions and discusses design trade-offs
- Iterates on the approach until you're satisfied
- Outputs a plan in `docs/plans/` with design decisions, file changes, and task breakdown

---

### Create PR

Squashes a feature branch into a single Conventional Commit, pushes, and opens a PR to main.

**Command:** `/pr-create`

**Features:**
- Reads the associated plan document and progress log for context
- Drafts a commit message explaining motivation and key decisions
- Asks for your approval before committing
- Rebases onto main before pushing so pr-merge can fast-forward
- Handles force-push when the branch was previously pushed with unsquashed commits

---

### Merge PR

Merges a PR locally via fast-forward to preserve your GPG-signed commits.

**Command:** `/pr-merge`

**Features:**
- Avoids GitHub's merge UI, which re-signs commits with GitHub's own key
- Fast-forwards main to the PR branch (rebases as fallback if needed)
- Stashes uncommitted changes and restores them after merge
- Cleans up remote and local branches, prunes stale remote-tracking refs

---

### Commit

Analyzes changes and generates atomic Conventional Commit messages.

**Command:** `/commit`

**Features:**
- Reviews staged and unstaged changes, groups them into atomic commits
- Drafts commit messages in imperative mood with type prefixes
- Updates stale documentation and optimizes imports before committing
- Presents a full plan for approval before executing any commits
- GPG-signs all commits, never adds AI attribution

---

### Document Data Flow

Generates or updates a data-flow architecture document (`docs/data-flow.md`).

**Command:** `/document-data-flow`

**Features:**
- Traces how data moves between components (content script, background, side panel)
- Produces step-by-step flow diagrams with data transition annotations
- Generates message protocol tables for all message types
- Follows strict formatting rules for consistency across updates

## Global Installation

Skills in this repository are only available when Claude Code runs inside it. To make them available across all your projects, symlink the `.claude/skills` directory into your global Claude Code config.

> If `~/.claude/skills` already exists, remove or rename it before creating the symlink.

### Windows

Run from the project root *as Administrator*:

```powershell
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills" -Target ".claude\skills"
```

### Linux / macOS

Run from the project root:

```bash
ln -s "$(pwd)/.claude/skills" ~/.claude/skills
```

## License

[GPL-3.0](LICENSE)
