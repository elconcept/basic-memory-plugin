---
name: basic-memory-nas
description: "Use for reading, searching, creating and organizing the user's self-hosted Basic Memory knowledge, project notes, decisions, checkpoints and memory handoffs through the remote NAS MCP server."
---

# Basic Memory (NAS) for ChatGPT

The user maintains the Basic Memory database on their own NAS. Connect to **only** the configured remote MCP server at `https://bm.xlap.pl/mcp`. Use the host's registered MCP tools; do not assume local processes, local repository files, Codex hooks, SSH, uv, uvx, Python CLI, or a local Basic Memory server are available. Never run shell commands or simulate a successful database write.

This ChatGPT skill adapts the Basic Memory workflows maintained in `elconcept/basic-memory-plugin` (the `bm-orient`, `bm-remember`, `bm-decide`, `bm-checkpoint`, `bm-share`, `bm-writing`, `bm-status`, and `bm-setup` skills) to ChatGPT's remote-tool environment.

## Establish the live connection

1. Discover the real Basic Memory MCP tools exposed in this conversation. First use the project-listing tool, commonly `bm_project_list`, or the available `bm_project` listing action. Do not invent a missing tool name or claim access based on this document alone.
2. If the server is unavailable, disconnected or requires authentication, report the exact connection blocker and do not fall back to a different, unapproved Basic Memory endpoint.
3. Scope every note operation to an explicit project. When several projects exist, use the user's selected project or ask which one should be read or written. Never silently switch to a default or broaden searches across unrelated projects.
4. If the existing context specifies the exact project unambiguously, reuse it. If there is no exact target for a destructive or sharing action, obtain clarification.

## Read and recall (bm-orient)

For a request to resume or find previous work, use the server's actual search/list/read tools, commonly `bm_search`, `bm_list` and `bm_read`. Resolve the exact note or checkpoint and cite its permanent link/identifier where present. Distinguish observed source content from interpretation. Do not claim a note exists without a tool result. Avoid retrieving entire unrelated projects.

## Capture a quick note (bm-remember)

For an explicit request to store or remember information in NAS, choose the intended project, preserve the exact useful facts, and use the server's actual write operation, commonly `bm_write`. Use an informative title and a short Markdown note with traceable context and date when applicable. Check the tool response and return the saved identifier/link. Do not claim a save was performed before the write succeeds. ChatGPT's own Memory is separate from this external NAS store.

## Record a decision (bm-decide)

Capture the decision, its rationale, considered alternatives where supplied, consequences, and relevant work or links. Use the confirmed target project. Do not invent missing rationale. Label interpretations as interpretations rather than as source facts.

## Create a handoff (bm-checkpoint)

Write a resumable project note including: task and objective; completed work; exact files, artifacts, decisions and links available from this conversation; outstanding steps; open risks; and what should happen next. Record a precise Basic Memory identifier and give a concise instruction to resume from it. Do not claim automatic session-start, pre-compaction hook, background capture or local Codex checkpoint behavior in ChatGPT.

## Share deliberately (bm-share)

Treat cross-project sharing as a write to the destination. Resolve source note and target project; obtain the user's authorization before modifying a team/shared project unless already explicit. Preserve origin, author and attribution where known; never silently copy personal notes to shared projects.

## Review status and setup (bm-status, bm-setup)

List actual reachable projects and available tools, optionally summarize recent relevant note counts after scoped searches. Report unavailable capabilities explicitly. The user's NAS MCP connection is the only runtime; **do not** install hook scripts, create `~/.codex/basic-memory.json`, adjust device policies, or ask for credentials in chat. Project names and write destinations must be derived from the live server/user input, not guessed.

## Writing standard (bm-writing)

Keep Markdown portable. Lead with conclusions, decisions and actionable state rather than boilerplate. Preserve user-supplied facts and citations; mark hypotheses. Use links to related notes when verified. Keep sensitive material inside the selected project; do not include it in unnecessary logs or search results.

## Verification

Separate four states: plugin archive published, plugin installed, MCP authenticated, and remote operation succeeded. One does not prove another. Report which operations were actually tested and which remain unverified.
