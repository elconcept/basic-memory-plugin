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

1. **Remote MCP reachable?** Call `bm_project(command="list")`; record whether it succeeds and the source connector. The client does not install Basic Memory CLI. Server diagnostics, if authorized, execute exclusively on NAS. If no MCP tool is available, mark the status unavailable; do not guess.



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
     `preCompactCapture` mode (default `extractive`), `sessionProfile` (default
     `general`), `repository` (coding profile only), `captureEvents` (default
     `true`).
   - From the **root** settings object (not `basicMemory`): whether `outputStyle` is
     `basic-memory` — i.e. whether the capture reflexes are on.

3. **Core hook health.** The original upstream hook CLI is intentionally not bundled. Until the reviewed T05 NAS adapter is installed and event-tested, report local checkpoint and hook status as **not implemented / unverified**. Never run `uvx` or a local Basic Memory daemon to simulate status.



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

- CLI:               basic-memory <version>
- Project:           <primaryProject, or "discovered project (not pinned)">
- Reads from (team): <secondaryProjects joined, or "none">
- Share targets:     <teamProjects keys joined, or "none">
- Capture folder:    <captureFolder>
- Remember folder:   <rememberFolder>
- Output style:      <enabled | not enabled>
- PreCompact:        <mode>
- Session profile:   <general | coding>
- Repository:        <owner/name or none>
- Event capture:     <enabled | disabled>
- Shared hook inbox: <path or unavailable>
- Shared pending envelopes: <count or unavailable>
- Shared archived envelopes: <count or unavailable>
- Pending checkpoint requests: <count or unavailable>
- Last flush:        <timestamp, never, or unavailable>
- Hook runtime:      basic-memory <version>; uv <version or missing>
- Recent checkpoints: <n across session and coding_session>
    - <title> — <permalink>
    ...
- Active tasks:      <n>
```

If there are no checkpoints yet, say "none yet" and remind the user that checkpoints
are written automatically before context compaction (and that a `primaryProject` must
be set for them to be written).

Warn when event capture is enabled and pending envelopes are accumulating or the
last flush is `never`, while noting that another harness may contribute to the
shared counts. Do not warn about an empty inbox when capture is disabled.
