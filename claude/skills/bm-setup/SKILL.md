---
name: bm-setup
description: Set up the Basic Memory plugin for this project — a short guided interview that configures the project mapping, seeds note schemas, learns or suggests placement conventions, and enables capture reflexes. Use when the user runs /basic-memory-nas:bm-setup, says "set up basic memory", or asks to configure/bootstrap the plugin.
argument-hint: (no arguments — runs an interactive interview)
---

# Basic Memory setup

Run a short, adaptive interview (~2-3 minutes) and then write the configuration.
Be conversational and **skip questions whose answer is already obvious** from
context (e.g. if `bm_project(command="list")` shows a single local project and no cloud
workspaces, don't ask about cloud/teams — just confirm). Suggest a sensible default
for every question so the user can accept with one word. Don't do any writes until
the interview is done and you've confirmed the plan.

## Prerequisite check

Basic Memory runs on a **self-hosted remote server** (NAS) reached through the
plugin's MCP connection. Call `bm_project(command="list")`. If the tool is missing or
errors, report the connector or OAuth problem and stop. Do **not** install Basic
Memory locally, start `uvx`, or add another MCP server: this build has no local
CLI by design.

## Interview

Ask only what you can't infer. Cover:

1. **Focus / how you'll use it.** "What will this project mostly be — code/dev,
   research, writing, knowledge capture, planning, or a mix?" This answer drives
   the folder structure you suggest (step 4) and is stored so the SessionStart
   brief can surface it. If you infer it instead of asking, state the use-case you
   assumed and the structure it implies so the user can correct it in one word.

   A code/dev answer makes this a **coding setup** (`sessionProfile: "coding"`):
   verify the directory is inside a Git repository, resolve a stable `repository`
   identifier such as `owner/name` from the origin remote or GitHub CLI, show it
   to the user, and ask for confirmation. Do not guess when the remote is missing
   or ambiguous, and do not infer `coding` merely because the current directory
   is a Git checkout — for mixed use, ask whether this repository should capture
   Git and pull-request context. The coding profile seeds the Coding Session
   schema so deliberate checkpoints carry required, queryable Git identity
   (repository, branch, SHA, and working directory), plus typed pull-request
   fields when a PR exists.

2. **Project mapping.** "Do you already have a Basic Memory project for this, or
   should I create one?"
   - Existing → show `bm_project(command="list")` and let them pick. That name becomes
     `primaryProject`.
   - New → propose a name (default: this repo's directory name) and create it with
     `bm_project(command="create", name="<name>", path="<path>")`.
     - *Local project* (default): path defaults to `~/basic-memory/<name>/`; any
       connected Basic Memory server can create it.
     - *Cloud project* (the user wants capture in a cloud workspace): pass the
       `workspace` selector (a slug from `bm_project(command="list")`) and a cloud-style path
       like `/<name>`, and create it with a **cloud-connected** MCP server. A purely
       local server (`uvx --prerelease=allow basic-memory mcp`) treats the path as a local directory and
       fails to create it (e.g. read-only `/`). When both a local and a cloud server
       are connected, route creation *and* the schema seeding through the cloud one,
       and pin `primaryProject` to the new project's `external_id` UUID
       (collision-proof across workspaces).

3. **Cloud / teams** (skip if there are no extra workspaces). Run
   `bm_project(command="list")`. If the user belongs to more than one workspace, they likely
   have a **team** workspace alongside their personal/default one. Use
   `bm_project(command="list")` to see the projects in each (note: project names collide
   across workspaces, so always use the **workspace-qualified name**, e.g.
   `my-team-2/notes`, or the `external_id` UUID — never a bare name).
   - **Read from the team** (recommended): ask which team projects to pull into the
     session brief for recall. Store their qualified names in `secondaryProjects`.
     These are **read-only** — recall reads across them; nothing is written to them.
     **Cap:** the SessionStart brief reads only the first **6** shared projects per
     session (a latency/output bound), in list order. If the user wants more than
     six, order the most relevant first and tell them the rest are configured but
     not read each session.
   - **Share target** (optional): if the user wants a place to *publish* notes to the
     team via `/basic-memory-nas:bm-share`, add it to `teamProjects` as
     `"<qualified-name>": { "promoteFolder": "shared" }`. Sharing is always a manual
     gesture — auto-capture never writes to a team project.

   Keep `primaryProject` a project the user owns for their *own* capture; team
   projects are for reading and deliberate sharing only.

4. **Placement — learn or suggest** (depends on the project's state). The goal is a
   short `placementConventions` string (3-6 lines) telling you where new notes go.
   How you get it depends on whether the project already has notes:
   - **Existing project with notes** → *learn*. Inspect it: `bm_list(path="/", project="<primaryProject>")` for the
     top-level folder layout (`bm_find` for recursive discovery), sample a few notes per folder (and, where a folder holds
     recurring typed notes, you may run `bm_schema(command="infer")` to see their shape).
     Summarize the *real* conventions — folder-by-topic layout, naming style, the
     observation categories they favor. Infer from their actual notes; don't impose.
   - **New or empty project** → *suggest* (there's nothing to learn yet). Propose a
     **light** structure that fits the focus from step 1 — 3-5 optional top-level
     folders, no deep taxonomy — and be explicit that it's a starting point, not a
     scaffold: notes work fine without it and structure can stay emergent. Don't
     create empty folders; folders appear as notes land in them. Let the user edit
     or decline in one word.
   Either way, keep it short and store the result as `placementConventions`. The
   SessionStart brief surfaces it (alongside `captureFolder`), so this is what makes
   your captures land where the user expects — without it, placement is guesswork.

5. **Schemas.** "I'll add the session schema for this profile, plus decision and
   task schemas, so I can find them precisely later — okay?" (See "Seed the
   schemas" below.)

6. **Lifecycle-event capture.** Not available in this build: upstream records it
   through the local CLI, which a remote NAS setup doesn't have. Skip the question
   and omit `captureEvents`.

7. **How active should I be? (output style)** "Want me to proactively capture —
   search the graph before recalling, write material decisions as typed notes, and
   cite permalinks? Or keep it quiet (just the session brief, plus
   `/basic-memory-nas:bm-remember` and `/basic-memory-nas:bm-checkpoint` on demand)?" Enabling it sets
   `outputStyle: "basic-memory"`. Default to enabled; leave it off for a recall-only,
   low-noise setup. (This is the single knob for how proactive the assistant is —
   the hooks always run regardless.)

8. **Extra skills** (optional, default no). "Want the optional `memory-*` toolkit
   (`memory-notes`, `memory-tasks`, `memory-schema`, `memory-defrag`, …)?" In this
   build they ship as a separate plugin, `basic-memory-nas-extras`, in the same
   marketplace, so the core stays as lean as upstream. (See "Optional extras" below.)

## Apply (after confirming the plan)

### 1. Seed the schemas
The plugin ships seed schemas at `<plugin>/schemas/` — that's **two directories up
from this skill's directory, then `schemas/`** (this skill is at
`<plugin>/skills/bm-setup/`). Read `coding-session.md` for a coding profile or
`session.md` for a general profile, then read `decision.md` and `task.md`.

These schemas cover notes the Claude integration writes directly.

For each one:
- Check whether the chosen project already has a schema for that type
  (`bm_search` with `filters={"type": "schema"}`, or try
  `bm_read("schemas/<name>")`). **If it exists, skip it** — never overwrite a
  schema the user may have customized.
- Otherwise write it with `bm_write`, routed to `primaryProject` (pass it as
  `project`, which accepts a name, workspace-qualified name, or `external_id` UUID):
  - `directory="schemas"`, `note_type="schema"`, `title` = the schema's title
    (Session / Decision / Task).
  - `content` = the markdown **body only** — everything *after* the `---`
    frontmatter block (the `# Session` heading and the prose).
  - `metadata` = the schema's structured frontmatter as a **nested dict**: `entity`,
    `version`, the full `schema` map, and `settings` (keep its nested `frontmatter`,
    and pass enum values as JSON arrays, e.g. `["open","resumed","closed"]`).
  - **Do not** put the schema's `---` frontmatter inside `content`. On the cloud
    write path that nested YAML is silently coerced to the string `'[object Object]'`
    (basic-memory-cloud#1000), corrupting `schema`/`settings`. The `metadata` param
    round-trips correctly on both local and cloud. After seeding, verify one note
    with `bm_read(..., output_format="json", include_frontmatter=true)` —
    `schema`/`settings` must come back as nested objects, not strings.
- **Coding setup:** the selected `coding-session.md` schema's Git identity fields
  (`repository`, `repo_root`, `cwd`, `branch`, `git_sha`) are required by design.
  Required-and-proven fields are what make coding checkpoints queryable, so seed
  the schema unmodified instead of also seeding the general Session schema.

### 2. Optional extras (if the user opted in)
Tell the user to install `basic-memory-nas-extras` from the same plugin
marketplace as this plugin. Do not run `npx`, copy skills into `~/.claude/skills`,
or install the official cloud plugin: one copy of each skill per surface.

### 3. Write settings
Build the `basicMemory` block from the interview:

```json
{
  "basicMemory": {
    "primaryProject": "<chosen>",
    "secondaryProjects": [],
    "captureFolder": "sessions",
    "rememberFolder": "bm-remember",
    "recallTimeframe": "3d",
    "sessionProfile": "coding",
    "repository": "owner/name",
    "placementConventions": "<learned or suggested summary, or null>",
    "teamProjects": {}
  },
  "outputStyle": "basic-memory"
}
```
Persist `sessionProfile` explicitly. Persist `repository` only for the `coding`
profile, after the user confirms it — a coding setup is incomplete without a
repository identifier because the `coding_session` schema requires queryable
Git identity fields. Omit both keys' example values for a `general` setup
(`"sessionProfile": "general"`, no `repository`).

Only include `outputStyle` if the user opted in. Ask whether this is a **team
default** (write/merge into `.claude/settings.json`, suggest committing it) or
**personal** (`.claude/settings.local.json`). **Merge** into any existing file —
read it, add/replace only the keys above, preserve everything else. Use compact,
valid JSON.

Writing the `basicMemory` block is also what stops the SessionStart hook's first-run
nudge — the config's presence is the signal that setup has run.

### 4. Smoke-test the wiring
Before you close, prove recall resolves through MCP — this catches a misnamed
project or a ref that doesn't route while the user is still here to fix it.

- **Primary:** `bm_search` with `filters={"type": "decision", "status": "open"}`,
  `page_size` 5, `project=<primaryProject>`. `0 results` is fine; an **error** means
  the ref doesn't route.
- **Seeded schemas:** `bm_search` with `filters={"type": "schema"}` in the same
  project should return the schemas you just seeded. For a coding setup, confirm
  the `Coding Session` schema is present.
- **One shared project** (only if `secondaryProjects` is non-empty): the same
  open-decision query against the first ref.

If a query errors, surface it and fix the project ref before closing.

## Close

Confirm what you did in a few lines: the project mapping, the session profile
(and confirmed repository for a coding setup), which schemas were seeded vs.
already present, whether placement was learned or suggested, the smoke-test
result, and whether the output style is on.

Then handle activation based on the output style:
- **Output style enabled** → it's fixed at session start, so the full capture
  reflexes only take effect next session. Prompt the user to **restart the session**
  (start a new Claude Code session) to activate them. Be precise so it doesn't read
  as "nothing works yet": the session brief picks up the new settings at the
  next start too, and `/basic-memory-nas:bm-checkpoint` works now — only the
  proactive-capture reflexes wait for the restart.
- **Output style off** → no restart needed; the hooks already run.

End with: *"Done — I'll use this from the next message. Run `/basic-memory-nas:bm-status`
anytime to see what I'm tracking."*
