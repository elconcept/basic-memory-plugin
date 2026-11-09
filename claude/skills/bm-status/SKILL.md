---
name: bm-status
description: Show the Basic Memory plugin's current state for this project — active project, capture folders, output style, recent session checkpoints, and whether Basic Memory is reachable.
disable-model-invocation: true
---

# Basic Memory status

Report the plugin's current state for this project, then present a concise summary.
This is a quick diagnostic — gather the facts and lay them out; don't over-investigate.

When no project is pinned, discover projects with `bm_project(command="list")`
and pass the selected project's external ID as `project` on note/search calls.
With several addressable projects, these calls require an explicit scope even
when a default is configured.

## Gather

1. **Server reachable?** Call `bm_project(command="list")` and report whether it
   succeeds. This build talks to a remote server over MCP only; never run a local
   `basic-memory`, `bm` or `uvx`.

2. **Configuration.** Read the `basicMemory` block with the hooks' precedence.
   For the user-level base, append `settings.json` to the literal value of
   `CLAUDE_CONFIG_DIR` when that environment variable is present; do not trim it,
   expand `~`, or treat an empty value as unset. Use `~/.claude/settings.json` only
   when the variable is absent. Then the project's `.claude/settings.json` and
   `.claude/settings.local.json` override per key. Report the result, noting when
   a value comes from the user-level block versus the project:
   - From the `basicMemory` block: `primaryProject` (or note none is pinned — the
     listed default or sole project is selected explicitly), `secondaryProjects` (team/shared read sources),
     `teamProjects` (share targets for `/basic-memory-nas:bm-share`), `captureFolder`
     (default `sessions`), `rememberFolder` (default `bm-remember`),
     `sessionProfile` (default `general`), `repository` (coding profile only).
   - From the **root** settings object (not `basicMemory`): whether `outputStyle` is
     `basic-memory` — i.e. whether the capture reflexes are on.

3. **Hook.** This build ships one local SessionStart hook that reads the settings
   above and prints the session brief; it makes no network calls and keeps no
   state. There is no PreCompact capture, inbox or flush to report.

4. **Recent checkpoints.** `bm_search` with
   `filters={"type": "session"}`, `page_size` 5, scoped to `primaryProject`
   if one is set. When `sessionProfile` is `coding`, also query
   `filters={"type": "coding_session", "repository": "<configured repository>"}`,
   then merge, deduplicate, sort newest first, and keep the newest five. List them
   by title + permalink.

5. **Active tasks.** `bm_search` with
   `filters={"type": "task", "status": "active"}` — report just the count.

When scoping these queries to `primaryProject`, pass it as `project`, including
when it is an `external_id` UUID.

## Present

Lay it out like this (fill in real values; write "—" or a short note for anything
you couldn't determine, rather than failing the whole report):

```
## Basic Memory status

- Server:            <reachable | error>
- Project:           <primaryProject, or "discovered project (not pinned)">
- Reads from (team): <secondaryProjects joined, or "none">
- Share targets:     <teamProjects keys joined, or "none">
- Capture folder:    <captureFolder>
- Remember folder:   <rememberFolder>
- Output style:      <enabled | not enabled>
- Session profile:   <general | coding>
- Repository:        <owner/name or none>
- Recent checkpoints: <n across session and coding_session>
    - <title> — <permalink>
    ...
- Active tasks:      <n>
```

If there are no checkpoints yet, say "none yet" and remind the user that
checkpoints are written on demand with `/basic-memory-nas:bm-checkpoint`.
