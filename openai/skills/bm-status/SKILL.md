---
name: bm-status
description: Report the Basic Memory for Codex configuration, reachability, hook expectations, recent Codex checkpoints, and active tasks.
---

# Basic Memory For Codex Status

Gather a concise diagnostic. Do not over-investigate.

## Gather

1. Call `bm_project(command="list")` on the plugin's remote MCP. Report reachability and explicit active project, or `unavailable` on an error. Never run local `bm`, `uvx` or `basic-memory`.
2. Read the existing `~/.codex/basic-memory.json` and optional project settings **only if accessible**; never invent configuration. Do not change trust/approval settings.
3. Query `bm_search` in the explicitly selected project for recent `codex_session` and `coding_session` notes, active tasks and open decisions. If project identity or repository filter is missing, stop the relevant query rather than broaden it.
4. Report hooks as `not installed`: this build ships no Codex hooks, local inbox or CLI.
5. Never transmit private note content into logs or reports; use counts, identifiers and permalinks.

## Present

Use this shape:

```text
Basic Memory for Codex
- CLI: <version or missing>
- Project: <primaryProject or default>
- Reads from: <secondaryProjects or none>
- Share targets: <teamProjects or none>
- Capture folder: <captureFolder>
- Remember folder: <rememberFolder>
- Recall timeframe: <recallTimeframe>
- Session profile: <general | coding>
- Repository: <owner/name or none>
- Checkpoint on compact: <enabled | disabled>
- Event capture: <enabled | disabled>
- Shared hook inbox: <path or unavailable>
- Shared pending envelopes: <count or unavailable>
- Shared archived envelopes: <count or unavailable>
- Last flush: <timestamp, never, or unavailable>
- Hook runtime in this environment: basic-memory <version>; uv <version or missing>
- Desktop hook execution: <verified from context and checkpoint | unverified>
- Recent checkpoints: <count across coding_session and codex_session>
- Active tasks: <count>
- Open decisions: <count>
- Hooks: installed; trust review required in Codex
```

List recent checkpoints by type, title, and permalink when available. Warn when
event capture is enabled and pending envelopes are accumulating or the last flush
is `never`, while noting that another harness may contribute to the shared counts.
Do not warn about an empty inbox when capture is disabled.
