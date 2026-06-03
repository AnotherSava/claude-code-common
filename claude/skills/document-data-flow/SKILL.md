---
name: document-data-flow
description: Create or update the data flow architecture document (docs/pages/data-flow.md).
allowed-tools: Read, Glob, Grep, Write, Edit, Agent, Bash(git rev-parse:*)
---

# Document Data Flow

Create or update `docs/pages/data-flow.md` — a reference document tracing how data moves between the major components of the project.

## Context
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`

## Working directory

All paths in this skill (`docs/pages/data-flow.md`, any existing architecture docs you Read first) are relative to **Repo root** from Context. The cwd may be a subdirectory — prefix every Read/Edit/Write/Grep/Glob call with the Repo root value. Bare paths are cwd-relative and will silently create/read files in the wrong place.

## When to run

- After adding a new data pipeline or processing stage
- After changing message protocols or communication patterns between components
- After modifying serialization boundaries, API contracts, or adding new message types
- After introducing a new architectural layer or external integration

## Workflow

### Step 1: Discover the project architecture

Explore the codebase to identify:
- The major components or layers (e.g. API server, worker, database client, frontend, CLI)
- How components communicate (HTTP, WebSocket, message queue, function calls, IPC, events)
- Shared types, schemas, or interface definitions
- Entry points and data sources (user input, external APIs, scheduled jobs, file uploads)
- Key modules, their responsibilities, and which files implement each component

Use `Glob` and `Grep` to locate configuration files, route definitions, message handlers, type definitions, and module boundaries. Read the main entry points and any existing architecture docs.

### Step 2: Update the document

Update `docs/pages/data-flow.md` covering:
- Component overview (each major component, its role, and key files)
- Serialization and data format constraints (if any)
- Data flow diagrams for each major flow (e.g. request handling, event processing, data sync)
- Message or API protocol tables (all message/event types, endpoints, directions)
- Connection management, error propagation, and retry behavior

### General formatting rules

- Component names are capitalized: API Server, Worker, Database, Message Queue
- Component names in headers and flow diagrams use bold italic: `***API Server***`
- Component names in running text use italic: `*API Server*`
- Do not hardcode file paths in component headers — a component may span multiple files
- Each component section in the overview ends with a "Key files:" bulleted list with brief descriptions
- Component descriptions in the overview list responsibilities but should not include method names — save those for the detailed flow diagrams
- Method/function references must include their file or class prefix: `server.handleRequest()`, `JobQueue.enqueue()`. Lowercase prefix = module file, uppercase prefix = class. Omit the prefix only when all methods listed together belong to the same file/class and it is specified explicitly.

### Formatting rules for data flow diagrams

Each flow section has this structure:
1. **Summary paragraph** — what this flow does, in 1-2 sentences
2. **Triggers** — bulleted list of what initiates this flow
3. **Horizontal rule** (`---`) — separates the description from the flow steps
4. **Flow steps** — alternating component headers and numbered action lists

**Component headers** in flow steps use bold italic on their own line:

```
***API Server***
```

**Action lists** are numbered Markdown lists under each component header. Include
method names with file/class prefixes:

```
***API Server***

1. Validate the incoming request via `server.validatePayload()`
2. Authenticate the caller and resolve permissions
3. Dispatch the job to *Worker* via the message queue
4. Return `202 Accepted` with a job ID to the caller
```

**Data transitions** between components use fenced code blocks with `⇩` prefix.
Each line inside the block starts with `⇩` followed by three spaces:

````
```
⇩   JobPayload (serialized as JSON):
⇩   { jobId, type, params, createdAt }
```
````

If no data is passed across a boundary, say so explicitly:

````
```
⇩   (no data passed)
```
````

**Key rules:**
- Do NOT mix actions and data — the code block region is only for data labels
- Data transitions always appear between two component headers
- Messages, events, and API calls are data — show them in code blocks

### Formatting rules for branching flows

When a flow branches (e.g., synchronous vs asynchronous processing, success vs failure), use an HTML `<table>` with:
- One column per branch, headers (`<th>`) describing each branch
- One row per component step — each cell contains the data received (code block) then the component name and its actions
- Use `valign="top"` on `<td>` elements so shorter branches align to the top
- Empty `<td></td>` for rows where only one branch continues
- Use Markdown inside `<td>` (with a blank line after the opening tag) for formatting
- Each component gets its own row to keep numbered lists independent

### Step 3: Verify

- Ensure all message types, event names, or API endpoints from the source code appear in the protocol tables
- Ensure new data pipelines are represented in the flow diagrams
- Check that the document is consistent with actual code
