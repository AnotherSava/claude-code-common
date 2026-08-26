# Global Guidelines

Never use absolute paths in committed documentation (README, CLAUDE.md, docs/, comments, and any committed memory or learnings files). Use relative paths for files within the project and generic descriptions for external references (e.g. "the BGA extension repo" not `D:\projects\bga\assistant`). Absolute paths are machine-specific: they break for other contributors, and for the user themselves — these repos are used from both a Windows and a macOS machine, so a `D:/projects/...` pointer is wrong on one of them.

Always ask clarifying questions before implementing if anything is ambiguous or unclear.

Never add "Generated with Claude Code" attribution (or any equivalent self-promotion) to text you author: PR descriptions, issue bodies, comments, commit messages, docs, etc. Leave it out entirely unless the user explicitly asks for it.

When presenting text the user is meant to copy verbatim — a form-field value, commit message, prompt, config snippet, sign-up blurb — wrap it in a fenced code block (```), never a Markdown blockquote (`>`). The terminal renders the blockquote marker as a left-side `|` gutter that gets swept into the copy and corrupts the paste; a fenced code block copies cleanly. Reserve blockquotes for text meant to be read, not copied.

When a copyable string has a part the user must replace with their own value, mark that part with a `{{insert-here}}` placeholder rather than a plausible-looking fake, an ellipsis, or a bare label. Use a short kebab-case hint inside the braces when it clarifies what goes there (e.g. `{{tvdb-api-key}}`). The double-brace form is unmistakably a placeholder — it won't be mistaken for a real value or copied verbatim by accident. Example: `doppler secrets set TVDB_API_KEY={{insert-here}} -p whats-next -c dev`.

## Self-Sufficiency

Before asking the user to do something (run a command, edit a file, check a value), figure out how to do it yourself. If the action is non-destructive, just do it. If it's destructive or irreversible, ask the user for permission — but propose the concrete action, don't ask the user to perform it.

**Configure services through their API, not by handing the user UI steps.** When a task means changing a third-party service (DNS/registrar, email provider, cloud host, SaaS admin, etc.) and that service exposes an API, drive the API yourself instead of walking the user through dashboard clicks. Find credentials before asking for them — the documented ad-hoc store is Doppler `tools/prd` (see the `refs-private` memory), which already holds keys for services like Porkbun. Do the read-only discovery immediately (validate the keys, retrieve current state); for outward-facing or destructive writes, show the concrete diff and apply on the user's go-ahead. Only ask the user to do the part the API genuinely can't reach — generating a key that doesn't exist yet, or flipping a per-account setting the API can't toggle.

Before asking the user *for missing context*, search past conversation history. A request that assumes shared knowledge I don't have ("my schedule spreadsheet", "that script we fixed", "the usual config") almost always refers to something established in an earlier session. Transcripts live in `~/.claude/projects/<slugified-cwd>/*.jsonl` — one file per session, and other project directories are worth checking when the topic isn't repo-specific. Grep them for the distinguishing term rather than reading whole files; they run to hundreds of KB each. Ask only after that comes up empty, and say what I already searched. Every entry also carries a timestamp, so the transcript answers *when* something happened and how long ago — never claim elapsed time is unobservable.

When changes are ready to test, run the project's `deploy` command (or equivalent) yourself via Bash. Do not suggest the user "run `deploy`" or type `! deploy`. The Self-Sufficiency rule applies: invoke the action, don't outsource it.

Don't give up on an explicit instruction the moment it hits a minor difficulty (a tool not loaded, a server not connected, an auth step, a missing dependency). Exhaust the ways to clear the obstacle *on the requested path* yourself first — install it, configure it, authenticate it. A workaround or alternative approach is NOT one of those ways: it's a different direction, and you don't take it unilaterally. If you genuinely can't clear the obstacle on the requested path, stop and confirm with the user before falling back to any alternative or abandoning the instruction. Silently substituting a workaround for what was explicitly asked is not acceptable — the user chose that path deliberately.

**Retry `API Error: Connection closed mid-response. The response above may be incomplete.` automatically — wherever it is yours to retry.** It is transport flakiness, not a real failure: the work was usually done and only the response was lost. Treat it like a 503 — retry silently rather than reporting it, abandoning the step, or switching to a different approach. Retry up to three times; only surface it if it still fails, and then say how many attempts were made.

- **Subagents:** re-issue the same call. Before assuming the work is lost, check the agent's transcript — a large structured return value is the most common thing to die, and the research behind it may be recoverable.
- **Workflows:** relaunch with `Workflow({scriptPath, resumeFromRunId})`. Unchanged `agent()` calls replay from cache, so only the dead ones re-run.
- If the *same* step dies three times, stop retrying and say so. Repeated death in one place usually means an oversized structured output; a leaner schema is the fix, not another attempt.
- **When my own turn dies, it is not mine to retry — do not claim otherwise.** Claude Code already retries automatically when the drop lands before any block completes; once a text block or tool call has finished it deliberately stops instead, so a completed tool call is never re-run. By then the turn is over and I am not running, so no instruction and no hook can resume it — `StopFailure` fires on exactly this but cannot block. Recovery is the user's `continue`, which resumes from the last completed block; it is the better word than `retry`, which reads as a fresh instruction and can redo finished work.

Exclude `node_modules/` from all file and content search patterns — it clogs results with false positives.

Do not inline Python scripts into Bash commands via `python -c`. Instead, use a heredoc: `python <<'EOF' ... EOF`.

Do not add logic, data structures, classes, or exports to production code that exist only to support tests. Tests should exercise the public API and real behavior — not rely on test-only hooks, flags, exports, or types in production modules.

## Research Before Trial-and-Error

**Check `~/.claude/learnings/` before diagnosing, not after.** It is indexed by filename, so a service or tool almost always has a file named after it. Read it *before* concluding that a credential is dead, an API is broken, or a thing cannot be done — those files exist precisely because each of those conclusions was once wrong. Real case: a Cloudflare token was reported to the user as invalid on the strength of `/user/tokens/verify` returning `Invalid API Token`, while `cloudflare-pages-deploy.md` already recorded that account-scoped tokens return exactly that *while being valid*. The token worked; the retraction was avoidable by reading one file. A negative result from a single probe is a reason to check what is written down, not a finding to report.

When a problem resists the first attempt or two — especially browser/CSS quirks, framework behavior, tool errors, or library/API limitations — search the web for the root cause and known fixes instead of iterating blindly or concluding it can't be done. A targeted search often surfaces a proven solution, and explains *why* the naive attempts failed, faster than guess-and-check. Lean toward researching early when the territory is unfamiliar or a fix isn't converging; reserve trial-and-error for cases where simply trying it is genuinely cheaper than a search. The repeated-experiment smell (three tweaks, three failures) is the signal to stop and look it up.

## Git Workflow

- Do not create git commits unless explicitly asked
- Do not push to remote unless explicitly requested
- **Creating a remote repository is not a commit or a push.** When asked to create a repo (`gh repo create`) and/or "set this folder to track the remote main branch", create the repo and wire up the remote/upstream — but do NOT make an initial commit and do NOT push existing work to it. "Track the remote main branch" configures the upstream ref; it is not authorization to push content. Leave committing and pushing as separate, explicitly-requested steps (normally via `/commit`). Wait for an explicit push/commit request before anything lands on the remote.
- When you've finished non-trivial feature work and the user pivots to a different feature, ask whether they want to commit the finished work first — don't start the new task on top of an uncommitted change set without offering. Skip the prompt for trivial edits or when changes are already committed.
- Do not ask whether to commit merely because you finished working — completing a task is not a trigger. The only trigger is the user pivoting to a next, unrelated set of changes (see the previous rule).
- When a task incidentally changes a file in a *different* repository than the one the task is about (e.g. editing a global skill in the dotfiles repo while working in a project), report the change so the user knows it's there — but do not offer or ask to commit it. Leave the other repo's commits entirely to the user; surface, don't solicit.
- Follow `~/.claude/skills/shared/commit-message-rules.md`
- Prefer `git status --short` over `git diff --stat` for change-set summaries. Changes sit unstaged until `/commit` runs, so untracked files are part of the pending commit — and `git diff --stat` silently omits them, producing an incomplete picture.
- **Check the remote before starting a new request that follows an idle gap.** When a request arrives roughly 30+ minutes after the previous one — the session transcript's last two timestamps give the gap — run `git fetch -q && git log --oneline HEAD..@{upstream}` before touching anything; a "no upstream configured" error just means there is nothing to sync. These repos are worked on from both a Windows and a macOS machine, so an idle gap is exactly when the remote moves ahead, and a stale tree means rebuilding what already exists upstream, or a `/commit` that cannot push. When the remote is ahead, read the incoming commit messages before diagnosing anything — they often explain the environment you are about to fight (a dev server pinned to one port, a publish workflow) — and propose a rebase rather than running one.

## Bash Commands

- **Windows (Git Bash):** always use forward slashes (`/`) in paths, not backslashes (`\`). Backslashes are interpreted as escape characters by bash and get stripped.
- **macOS / Linux:** paths are already Unix-style; no special handling needed.
- **File tools share the Bash cwd.** Read/Edit/Write/Glob/Grep resolve relative paths against the current Bash working directory, and a `cd` in an earlier Bash call persists across calls — a stray `cd` then silently misdirects file writes (e.g. into a nested `repo/repo/…` tree). Use absolute paths for file tools, or avoid `cd` (use `--prefix`, `-C`, or a `( cd … )` subshell).

When asking the user to run a command manually (e.g. launching an app, system config):
- **on Windows:** provide PowerShell syntax — not bash or cmd.
- **on macOS / Linux:** provide bash/zsh syntax.
- **Never route a plaintext secret through the `!` prefix.** A command the user runs via `!` has its full text — the secret value included — recorded in the session transcript/logs. When a command must carry a secret value (`doppler secrets set KEY="…"`, an API key, a token, a DB URL), have them run it in a **separate terminal outside Claude Code**, or use the service's dashboard — never `!`. `--silent`-style flags hide command *output*, not the `!`-recorded *input*.

### Background processes I spawn

When I launch a process that outlives the command and that I'll kill later myself (a headless browser, a dev server, a daemon):
- **Redirect its output.** Detach stdout/stderr to a log file or the null device (PowerShell: `Start-Process … -RedirectStandardError <file>` or wrap in `cmd /c "… >nul 2>&1"`; bash: `… >/tmp/x.log 2>&1 &`). Otherwise the process's async messages — GPU/SwiftShader warnings, crash/shutdown lines — leak into the user's terminal, often after my turn ends. This has happened repeatedly with headless Chrome.
- **Kill the whole tree, not just the parent.** Such processes fork children (headless Chrome spawns GPU/renderer subprocesses that keep emitting after the parent dies). Match every related PID by a distinguishing flag/profile/temp-dir I chose (e.g. `--headless` or my `--user-data-dir`), not the parent PID alone — and never by a pattern that could match the user's own running instances (their normal browser, their dev server).
- **Clean up before reporting done.** Remove temp profile dirs, scratch files, and any served generator pages, and confirm zero leftover matching processes.

## Tooling Defaults

- **Node.js**: default to the current active LTS (Node **24** as of May 2026) for new projects, CI workflows, and `.nvmrc` files — unless the project already pins an older version, a dependency demands otherwise, or there's a specific reason to use something else. Always prefer an existing `.nvmrc` / `engines.node` over this default.
- **Package-manager pin**: any project with a `package.json` should pin its toolchain via the `packageManager` field (e.g. `"npm@11.17.0"`) with Corepack enabled, so every machine and CI run uses an identical manager version — an unpinned npm drifts the lockfile across machines (`peer: true` markers, `devOptional`→`dev` churn). Offer to add it when missing rather than pinning silently; bump it deliberately like a dependency (typically alongside a Node upgrade), not on every release. Resolve the current stable with `npm view npm version` and avoid prerelease majors. See `~/.claude/learnings/corepack-packagemanager-pin.md`.
- **Engine enforcement**: a project that declares an `engines.node` range should also set `engine-strict=true` in its `.npmrc`. npm treats `engines` as *advisory* by default — it prints a warning and installs anyway — so a declared pin, an `.nvmrc` and a README can all agree while someone silently builds on the wrong runtime. The failure then surfaces far from its cause: a Node-24 install of a Node-22 project presented as 245 unrelated-looking TypeScript errors, not a version complaint. Offer it when adding or noticing an `engines` field; it is one line, and it turns a silent mis-build into `EBADENGINE`.
- **License**: default to **MIT** when a project needs one — a `LICENSE` file at the repo root with the current year and the user's name (from git config). It's a default recommendation, not an imposition: since the choice is legally the user's, confirm before adding, and defer to copyleft/GPL, a company/CLA policy, or an existing license when the project calls for it. The trigger is a repo about to be published or shared without a license, not every scaffold. **For a repo that is private, default to all rights reserved instead** — with no copies out, copyright's default already governs and granting nothing preserves every path, whereas MIT sitting in a root commit is a real grant that takes effect the moment the repo is shared or opened. `/github-create` offers both as a first-class choice and seeds whichever is picked; the relicensing rules and the source-available options are in `learnings/software-licensing-choices.md`.

## Best-Practice Adoption

When a project lacks a practice that is standard for its type — a linter for a Python project, ESLint/strict tsconfig for TypeScript, CI for a released library, a lockfile, a test runner, or a `.claude/commit-checks.sh` running whatever actually gates the deploy in a repo that commits straight to `main` — point out the gap and offer to adopt it. Offer, don't adopt silently; and don't nag: one offer per project, and if declined, record the decision in project memory so it isn't re-raised.

When the offer is accepted:
- **Measure before proposing rules**: run the candidate tool against the codebase and triage the real baseline per rule; adopt with a clean baseline (fix or explicitly scope every existing violation).
- **Fit the tool to the project's documented style**, never the reverse — skip or configure rules that fight an established preference, and document every deliberately disabled rule and its reason inside the tool's config file.
- **Prefer enforcement at generation time** (e.g. a PostToolUse lint hook) over conventions that rely on remembering to run something.

## Sharing a Host With Another Project

Several of these projects run as co-tenants on one box behind one reverse proxy. That arrangement has one failure mode, it is silent, and it has already cost 41 hours of a commercial site serving a neighbour's application — with HTTP 200, healthy containers and a valid config throughout. Two rules prevent it; `~/.claude/learnings/docker-compose-shared-host-co-tenancy.md` has the mechanics and the ready-made checkers.

- **Never take a generic name in a namespace someone else shares.** Compose publishes a *service's* name as a DNS alias on every network it joins, so `app`, `web`, `db`, `caddy` and friends are claims staked on a shared bridge, not local labels. The same applies to any flat shared namespace: a vhost dropped into a common `conf.d` is separated from its neighbours only by its basename, so `site.caddy` overwrites theirs. Name the thing after its project (`scheduler-app`, `scheduler.caddy`), make the service name equal the container name, and dial upstreams by container name, never by service name.
- **Verify identity, not liveness.** On a shared proxy a 200 proves *something* answered, never that it was yours — which is exactly why every conventional check stayed green. Assert a marker the origin app emits (a `<title>`, a dedicated identity route), and assert every *other* tenant's marker is absent; the second half is what turns "up" into "up and correct". Anything the proxy adds — status code, `Server` header, the certificate — stays correct while it routes to the wrong app.

The same shape recurs beyond compose: any time a name is resolved from a namespace shared with things you do not control, ask which one wins, and make the answer not matter.

## Overused Phrases

A live list of phrases I lean on too heavily. They are banned in all authored text — chat responses, commit messages, PR and issue bodies, docs, comments. Replace each with a plain, specific alternative rather than a synonym of the same reflex. The list grows: when a new tic surfaces, add it here with its replacement. Rationale in `~/.claude/memory/feedback_overused_phrases.md`.

- **"landed"** — banned in every sense, not just the merge/ship one. Also covers a feature being implemented ("the retry logic landed in `client.ts`"), a fix taking effect, or a value settling. Say what actually happened instead: "added", "implemented", "merged", "committed", "is in `main`", "now lives in `client.ts`".
- **"smoking gun"** — with the rest of the detective register: "the culprit", "case closed", "caught red-handed", "the plot thickens". Name the evidence and what it shows: "the log records the move", "this line is what does it", "that confirms it".
- **"earn its keep" / "earned its keep"** — and the same reflex in "paid for itself", "worth its weight". State the result instead: "the review found four defects", "that check caught the truncated file", "worth running".

## Code Style

### Formatting

- Leave an empty line at the end of every file
- Prefer single-line expressions over multi-line formatting, even if they're long. **Exception**: multi-line is acceptable when calling functions/constructors with all named parameters.

### UI Text Casing

Default to sentence case for user-facing UI strings (menu items, buttons, dialog titles, tooltips, notifications). Capitalize only the first word and proper nouns/acronyms. Examples: "Open config file", "Hide with Esc", "Start with Windows". See `~/.claude/memory/feedback_sentence_case_ui.md` for rationale and edge cases.

### Prose Style

In prose (docs, READMEs, comments), don't open a sentence or line with code-formatted (backtick-wrapped) text when regular text follows — lead with a real word and fold the code reference in after it ("The `notifications` block controls…" not "`notifications` controls…"). Term-definition list items where the code identifier is the subject are the standard exception. See `~/.claude/memory/feedback_no_code_at_sentence_start.md`.

Parallel enumerations should share grammatical form — list-item blurbs are all imperative verbs or all noun phrases, not a mix ("download …" / "explore …" / "build …", not "download …" alongside "a tour of …").

### Explicit State

Use a dedicated field or variable for object state rather than overloading another field's values (e.g., using `internalDate === 0` as a "deleted" sentinel). A simple null/non-null check is fine, but anything beyond that should be an explicit status field.

### Early Returns

Avoid adding early return guards like `if not items: return` when the function would behave identically without them (e.g., a `for` loop over an empty collection naturally does nothing). Only add early returns when they actually change behavior or prevent errors.

### Type Hints (Python)

Always specify parameter and return types.

### Import Organization

Place imports at the top of the file. Order (with blank lines between groups):
1. Standard library
2. Third-party
3. Local

Inline imports only for circular import resolution (add comment: `# inline to avoid circular import`) or `TYPE_CHECKING` blocks.

### Dependencies (Python)

When adding or removing a third-party import, update `requirements.txt` in the same change to keep it in sync.

### Refactoring Safety

When changing field/function names, search all usages (including tests) and update accordingly before making breaking changes. Run all tests after refactoring.

**Know which command is the real gate, and re-run *that* one — tests and lint usually are not it.** Before calling a change done, ask what the deploy actually runs, and run the same thing. A test suite proves behaviour and a linter proves style; neither type-checks, so a refactor can pass both and still fail the build. Two traps make this worse than it sounds:

- **A checker invoked outside the build can be structurally blind.** Frameworks that generate types *during* the build (Next's `PageProps`/`LayoutProps`, and anything else emitted into a build directory) leave a bare `tsc --noEmit` unable to resolve them on a clean tree — so the values they type degrade to `any`, and real errors disappear with them. The build is then the only honest check, and a separate `typecheck` script is worse than useless because it looks like one.
- **Filtering a checker's "known noise" filters the signal.** Grepping those unresolved-type errors out of the output also hides the genuine error sitting beside them, and piping a command through `grep` discards its exit code, so a failure reads as success. Assert on the exit status, not on the text you chose to keep.

The failure mode is quiet: verify, refactor, re-run only the cheap checks, ship. Real case — a `/clean-code` pass extracted a helper whose parameter type was narrower than the value passed to it. Lint and 333 tests passed; only the production build, which type-checks against generated route types, caught it.

### Single Source of Logic

When the same non-trivial computation or step-sequence is needed in two or more places, extract it into one function every call site calls — do not copy-paste it. Copies drift: a later fix or refinement lands in one and silently misses the others (real case: one path scaled a value by the DPI factor, its copy-pasted sibling forgot to, so the two positioned the same element differently). This matters most for **parallel code paths that must stay behaviorally/visually consistent** (two ways of placing or rendering the same thing) — give them a shared helper so they *cannot* diverge. When you touch code near a pre-existing duplicate, consolidate rather than adding a third copy. Balance against premature abstraction (`~/.claude/memory/feedback_no_premature_abstraction.md`): extract once 2–3 real call sites exist, not speculatively — but once they do, share, don't duplicate. Watch for the divergence smell during review: near-identical blocks whose only differences are *unintended* (a missing `* scale`, a different fallback constant).

**Confirm the path you're fixing is the one that runs.** Before shipping a behavioral fix, check that the function you changed is actually reached by the user action it's meant to affect — grep for callers. A duplicate whose twin is dead is the worst case of the above: the fix compiles, reads correctly, and changes nothing, because the live path is the other copy. (Real case: a tray Show/Hide had two implementations; the one wired to the frontend command had zero callers, so hardening it left every real click on the unfixed copy.)

## Gitignore

When adding entries to `.gitignore`, choose the right scope:
- **Global excludes** (`git config --global core.excludesfile` — on this machine `~/.gitignore`, not `~/.gitignore_global`): OS- or user-specific files no contributor shares — IDE folders, OS caches, tool outputs (`.idea/`, `Thumbs.db`, `.ralphex/`), and per-machine wrappers written by personal skills (the deploy/build/cleanup/publish/doppler skills' `scripts/*.sh` wrappers and the `config/*.env` files they read — see `git/gitignore` for the current set). Only narrow **root-anchored file** patterns belong here — never a floating whole-dir pattern like `scripts/`, which would hide that dir in *every* repo, including ones that commit a real `scripts/`. (A file pattern with a mid-string slash like `scripts/deploy.sh` is already root-anchored.)
- **Project gitignore** (`.gitignore`): files everyone who checks out the project should ignore — build outputs, `.env` files, `node_modules/`, `__pycache__/`, and project-structure-specific artifacts (e.g. a dev server's `<DEV_DIR>/dev-server*.log`). Anchor with a leading slash (`/scripts/`) unless matching at any depth is intended.

See `~/.claude/learnings/gitignore-anchoring-and-scope.md` for the anchoring rules and the per-project→global migration checklist.

**Crash dumps: delete, don't gitignore.** Transient crash artifacts — `*.stackdump` (Cygwin/Git-Bash), core dumps, `*.dmp` (Windows minidumps), `hs_err_pid*.log` (JVM), and the like — are one-off byproducts of a single crash, not recurring build output. Delete them when they turn up; do **not** add them to any gitignore. Gitignoring normalizes them as expected and silences the signal that something actually crashed. Exception: keep a specific dump only while you're actively analyzing that crash — and say you're keeping it — then remove it once done.

## Symlinks

Everything under `~/.claude/` is symlinked from the dotfiles repo (`CLAUDE.md`, `settings.json`, `skills/`, `hooks/`, `learnings/`, `memory/`, `scripts/`). The Write and Edit tools **refuse to write through symlinks**. Before editing any file under `~/.claude/`, resolve the symlink with `readlink <path>` and pass the real target path to Write/Edit.

For first-time global installation, use the platform-appropriate command block from `README.md`'s Global Installation section. For ad-hoc symlinks during a session:

- **macOS / Linux:** `ln -s` with an absolute target path (`"$(pwd)/..."`).
- **Windows:** Never create symlinks from Bash (`ln -s`) — it silently creates copies instead. Use PowerShell `New-Item -ItemType SymbolicLink` from an Administrator prompt. Use `$PWD` to build absolute target paths.

## Global Memory

Cross-project preferences and feedback. Memory files live in `~/.claude/memory/`. When saving a memory that applies across all projects (not just the current one), write the file there and add an index entry below. Same frontmatter format as project-specific memories.

**Project memory is version-controlled too.** Repos wired with `~/.claude/scripts/link-project-memory.sh` redirect their machine-local memory cache (`~/.claude/projects/<hash>/memory/`, a symlink) into a committed `<repo>/.claude/memory/`. So when saving *project-specific* memory: resolve the symlink and write to `<repo>/.claude/memory/`, then commit it with the rest of the work. On a fresh clone, re-run the script to re-establish the symlink. If a repo's cache is still a plain directory (not yet wired), run the script first.

- [User GitHub account](~/.claude/memory/user_github_account.md) — handle is `AnotherSava`; use to filter "my repos" vs third-party clones
- [Screenshots live on the Desktop](~/.claude/memory/user_screenshot_location.md) — "see the screenshot" with nothing attached means the newest PNG in `~/Desktop`; go look before saying none arrived
- [Follow skill instructions exactly](~/.claude/memory/feedback_follow_skill_instructions.md) — never abbreviate or skip steps in skills, even when output feels verbose
- [Fix failing skills](~/.claude/memory/feedback_fix_skills.md) — fix the skill definition instead of working around failures manually
- [Glob safety for numeric filenames](~/.claude/memory/feedback_glob_safety_windows.md) — `hex_4*.png` matches hex_40, hex_400, AND hex_441; use explicit ranges
- [Post-iteration cleanup audit](~/.claude/memory/feedback_post_iteration_cleanup.md) — before committing after a debug/optimize session, remove changes from disproven theories; don't leave cruft
- [Verify before justifying legacy behavior](~/.claude/memory/feedback_verify_before_justifying.md) — if explaining why old code/docs exist (especially defending keeping it), check the source before speculating; defensive guesses preserve cruft
- [Captured the lesson, drop the code](~/.claude/memory/feedback_research_to_production_cleanup.md) — when research code transitions to production, delete helpers whose rationale lives in docs
- [No permanent surface for one-time tasks](~/.claude/memory/feedback_no_permanent_logic_for_one_time.md) — do one-offs (backfills, migrations, seeding) as throwaways and delete; don't add a flag/helper/export to production — or a menu item/button to the UI — for a single run, and don't justify it with "single source"/"future use"
- [Stay silent on user `!` commands](~/.claude/memory/feedback_silent_on_bash_input.md) — a bare `!`/bash-input result is the user's own action; return control immediately, no analysis or "looks good" filler, unless they ask
- [Fix bugs at the source, not in callers](~/.claude/memory/feedback_fix_at_source.md) — if a bug lives in code I can modify (including vendored copies), fix it at the source instead of working around or suppressing it (gitignore, filtering, silencing)
- [Generalize global skills, don't fork project-local](~/.claude/memory/feedback_generalize_global_skills.md) — name collisions load the wrong SKILL body; but a skill whose domain IS one project belongs in its repo
- [No unsolicited past-data fixes](~/.claude/memory/feedback_no_unsolicited_data_fixes.md) — fix the going-forward code only; don't proactively migrate/correct stale stored data unless asked or after asking
- [Check for a live sibling session](~/.claude/memory/feedback_check_live_sibling_session.md) — an instruction that doesn't fit this repo likely belongs to another live session; grep widget.jsonl + git status there before editing its files; siblings also overwrite the shared clipboard
- [Native dialogs render plain text — no clickable links](~/.claude/memory/feedback_native_dialogs_no_links.md) — `tauri-plugin-dialog`/MessageBox/NSAlert can't embed `<a>`; build a custom Tauri webview window for About-style content with links
- [About dialogs describe WHAT, not HOW](~/.claude/memory/feedback_about_what_not_how.md) — About copy stays declarative ("Each session keeps a history"), not action-prescriptive ("Double-click to open")
- [Run the script, not the skill](~/.claude/memory/feedback_deploy_script_not_skill.md) — once configured, run `bash scripts/<verb>.sh` directly for deploy/build/cleanup/publish; Skill is for first-time setup; a new shell fn needs a restart
- [Overused phrases](~/.claude/memory/feedback_overused_phrases.md) — live blocklist of verbal tics; the list itself is the **Overused Phrases** section above
- [Use Doppler for secrets](~/.claude/memory/feedback_doppler_secrets.md) — **when a task touches secrets/keys/tokens/`.env`/encryption/Doppler, invoke the `/doppler` skill before planning secret storage or writing any project/config/command; this line is a pointer, not the answer.** Landmines it prevents: workplace `sava` ≠ a project (create/verify a per-app project via `doppler projects`); default config is **`dev`** (not `prd`); set with `doppler secrets set KEY="value" -p <proj> -c dev --silent` (quote the value); commit a `doppler.yaml`; offer don't impose
- [Text-control affordances](~/.claude/memory/feedback_no_underline_links.md) — strip resting underlines; shape carries meaning (link=hover-underline for WCAG 1.4.1, toggle=chevron, action=`+`, all icon/soft-fill-pill not underline)
- [Find the override before stacking a setting](~/.claude/memory/feedback_check_overrides_first.md) — a global setting that looks ignored is usually cancelled by a local rule; remove that rule instead of adding a redundant copy
- [Private references](~/.claude/memory/refs-private.secret.md) — encrypted (transcrypt); coordinates for ad-hoc third-party credentials Claude uses — read it when a task needs one (decrypted locally; opaque without the key)
- [Grep must survive markdown emphasis](~/.claude/memory/feedback_grep_markdown_emphasis.md) — `grep "Node 22"` misses `Node **22 LTS**`; sweep with a separator-tolerant pattern and search concepts, not just the phrase
- [Check a destination is not published](~/.claude/memory/feedback_check_destination_visibility.md) — before moving anything into a shared/dotfiles repo, check `gh repo view --json isPrivate` AND `git check-ignore`; untracked is not ignored
- ["Not run" must not look like "passed"](~/.claude/memory/feedback_not_run_is_not_pass.md) — a check that can't tell success from never-ran turns an open problem into a closed-looking one; probe the precondition, assert the artifact, print NOT COVERED
- [Write the procedure to find the missing artifact](~/.claude/memory/feedback_write_the_procedure.md) — review asks "is this right", a runbook asks "does this exist"; run the commands a doc quotes rather than predicting their output
- [No guessed facts](~/.claude/memory/feedback_no_guessed_facts.md) — don't state a guessed URL/path/endpoint as known; verify it or say you're guessing
- [No invented rationale](~/.claude/memory/feedback_no_invented_rationale.md) — asked to add a rule, record the rule and its replacement; don't supply a "why" you guessed
- [Live values = read the system](~/.claude/memory/feedback_live_values_source_of_truth.md) — rates/prices/config/deployed-state change without a commit; read the live source (DB/live page/doppler), never cite a doc snapshot as current
- [Machine coordinates](~/.claude/memory/machines-private.secret.md) — encrypted (transcrypt); Tailscale tailnet names/IPs for the user's machines, plus the SSH login for the Windows desktop — use these to make any project reach one machine from another, never `*.local` or LAN IPs; platform mechanics in `learnings/windows-openssh-over-tailscale.md`
- [Minimal UI chrome](~/.claude/memory/feedback_minimal_ui_chrome.md) — no duplicate state signals, no field help text, no card blurbs; icon over text button; state in a badge, never a placeholder
- [Empty state names the filter](~/.claude/memory/feedback_empty_state_names_the_filter.md) — say what the filter hid, never that nothing happened; "show everything" is one click away and disproves it
- [Desktop first, phone later](~/.claude/memory/feedback_desktop_first_then_phone.md) — no breakpoint tuning while the look is still moving; phone gets its own pass
- [Deploy and publish are separate verbs](~/.claude/memory/feedback_deploy_publish_separate_verbs.md) — `deploy` runs it here, `publish` ships it out; own script each, never `deploy publish`
- [No per-prompt hooks](~/.claude/memory/feedback_no_per_prompt_hooks.md) — never a hook on every prompt (worse if blocking); use an observable guideline or an on-demand check
- [Extend the schema, don't free-text it](~/.claude/memory/feedback_extend_schema_not_freetext.md) — data that doesn't fit gets a new field, offered and priced honestly, not stuffed into a comment
- [Compound label hierarchy](~/.claude/memory/feedback_compound_label_hierarchy.md) — a label made of several kinds of information gets a colour+weight per part, never one uniform run; a separator inside a part sits tighter than the gaps between parts

## Memos

While working on one task the user often surfaces ideas for *other* work — "we should also debounce that search box", "remind me to cache these responses". They want these parked, not acted on, and they want Claude to hold them rather than carrying them in their own head. Memos are the backlog for exactly that: lighter than a GitHub issue (a half-formed thought, not a tracked unit of work), kept in a single committed file, `<repo>/.claude/memos.md`, as a dated `- [ ]` checklist. The `/memo` skill owns the file format and the read/write mechanics.

**Capture — offer, don't impose, and don't act.** When the user drops an idea that isn't part of the current task, offer to memo it ("Want me to memo that?") and append it only on a yes. Never silently record, and never start on the idea — capturing it is the whole point of *not* doing it now. For deliberate captures the user runs `/memo <text>` themselves. Either way the entry lands in `.claude/memos.md` in the format the `/memo` skill defines. Don't confuse a memo with an instruction: if it's plausibly "do this now", ask which they meant.

**Surface at three moments.** The backlog comes back on its own so the user never has to remember it:
- **Session start / `/clear`** — the `memos-surface.py` hook surfaces the open items in the **status bar** only (a transient "what's next" reminder), numbered newest-first to match `/memo`. It injects **nothing** into chat — so you never greet with or push the backlog — and the matching `UserPromptSubmit` hook clears the bar the moment the user sends anything. When that first message is a bare number (or "memo N" / "start N"), the hook injects, bound to that message, which memo it maps to; act on it — start that memo as a fresh task and check it off when done. Any other first message just proceeds normally, with memos unmentioned.
- **Task completion** — when you finish a task during which one or more memos were captured, end the wrap-up with those memos as a numbered list and offer to start one. Don't begin any unasked.
- **Commit** — `/commit` lists the open backlog after the push, alongside its issue notice.

At task completion and commit, the offer is the same: present a numbered list, let the user pick one or leave them. Picking one begins a fresh task; mark its entry `- [x]` once genuinely done.

## Reference Material

Before reinventing a plugin or skill, and whenever you feel under-informed about the technology or domain at hand, consult the official Anthropic repositories:
- Plugins: https://github.com/anthropics/claude-plugins-official
- Skills: https://github.com/anthropics/skills

Browse them for existing implementations to reuse, adapt, or learn from rather than building from scratch.

## Skills

Skills live in `.claude/skills/<skill-name>/` (project-local) or `~/.claude/skills/<skill-name>/` (global). The entry point for each skill is `SKILL.md`.
