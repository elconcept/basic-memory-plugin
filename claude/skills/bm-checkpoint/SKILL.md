---
name: bm-checkpoint
description: Save a deliberate work checkpoint to Basic Memory with the story, changed files, verification, decisions, blockers, and the next action. Use when the user asks to checkpoint, wrap up, hand off, or remember the state of the work.
argument-hint: (optional short topic for the checkpoint title)
---

# Checkpoint Claude Work

Create a durable handoff note for the current work. Use this when the user asks
to checkpoint, wrap up, hand off, remember the state of the work, or before a
long context transition. This is the deliberate, high-signal counterpart to the
automatic PreCompact checkpoint.

When no project is pinned, discover projects with `bm_project(command="list")`
and pass the selected project's external ID as `project` on note/search calls.
With several addressable projects, these calls require an explicit scope even
when a default is configured.

## Automatic hook checkpoint mode (only when checkpoint_key is supplied)

This special mode is activated **only** by a Basic Memory NAS lifecycle hook
with an exact checkpoint_key value. It takes precedence over the deliberate
manual checkpoint format below; ordinary user-requested checkpoints still
follow all upstream rules, including immutable Codex checkpoint lineage.

1. **Resolve the project first.** Use the explicit project in the hook
   instruction, or confirm the sole/default project through bm_project. In this
   vanilla NAS installation the verified default is main. Never write to a
   secondary project or reuse a note from another project.
2. **Read source material.** Read all listed local material_files completely
   before composing the checkpoint. If NONE, record the capture failure and
   use only available current context. Do not invent lost details. Preserve
   every decision candidate as a decision or explicitly classify it as not a
   decision, with justification. State whether source capture was partial.
3. **Idempotency.** Search this same project using structured metadata filter
   checkpoint_key=<exact ck>. If no matching note exists, create one using
   bm_write with note type session or coding_session and frontmatter fields
   checkpoint_key, session_id, seq, trigger, capture, material_complete.
   **Include a separate exact body line**: checkpoint_key: <exact ck>.
   If a matching note already exists, read it and only append missing
   checkpoint material via bm_edit according to the installed bm_man contract;
   never overwrite the full note or edit an unrelated checkpoint.
4. **Required structure.** Cover Problem, Approach, Decisions, Changes,
   Artifacts (file paths, commit SHAs, PRs), Verification (only checks actually
   run), Open Questions/Blockers, Next Action and Source Material. Distinguish
   direct user statements, independently verified findings and interpretations.
5. **Readback is mandatory.** After the write/edit, obtain the exact note
   identifier from the tool result, call bm_read on that identifier with the
   same explicit project, and confirm that its body contains the exact line
   checkpoint_key: <exact ck>. If any step is unavailable, report failure.
6. Do not run local basic-memory, uvx, Docker, SSH or a separate MCP connection
   to save the checkpoint. The plugin's trusted PostToolUse hook decides
   whether local status becomes saved. **A model declaration or the existence
   of a permalink alone is not confirmation.** Do not invoke the terminal-only
   bm_hook.py confirm. For a client without PostToolUse support, an authorized
   report action means reported_by_model, never saved.

This hook mode is an emergency continuity path, not a substitute for durable
bm-decide and bm-remember notes recorded during normal work.

## Gather

Resolve config: read the `basicMemory` block with the same precedence the hooks
use. For the user-level base, append `settings.json` to the literal value of
`CLAUDE_CONFIG_DIR` when that environment variable is present; do not trim it,
expand `~`, or treat an empty value as unset. Use `~/.claude/settings.json` only
when the variable is absent. Then the project's `.claude/settings.json` and
`.claude/settings.local.json` override it per key:

- `primaryProject`, optional; discover and explicitly select the listed default or sole project when absent
- `captureFolder`, default `sessions`
- `placementConventions`, optional
- `sessionProfile`, default `general`
- `repository`, required when `sessionProfile` is `coding`

Apply the `bm-writing` skill before drafting the note.

Gather evidence:

- the original problem or goal and why it mattered
- the approach taken and why it solves the problem
- the current system state and practical impact
- tradeoffs, sharp edges, useful simplifications, and intentionally parked work
- the durable lesson, if one exists — what future work should know or avoid
- `git status --short`
- current branch
- repository root and current working directory
- current Git SHA
- current pull request number, title, URL, state, base, and head when one exists
- changed files you touched
- tests or checks actually run
- failures or skipped checks
- decisions made in this session
- unresolved blockers
- next action
- current username, hostname, and timestamp
- exact host-provided session identifier, when available; never infer one

Do not claim a test passed unless you ran it or the user supplied the result.

## Write

A checkpoint is a durable handoff, not a status dump or commit-by-commit
changelog. Tell the story for a human or agent returning later.

Write the note with `bm_write`, routed to `primaryProject` (pass it as
`project`, which accepts a name, workspace-qualified name, or `external_id` UUID). For the `general`
profile:

- `title`: `Claude checkpoint - <short topic>`
- `directory`: configured `captureFolder`
- `tags`: `["claude", "checkpoint"]`
- `note_type`: `session`
- `metadata` (frontmatter):
  - `status: open`
  - `project: <primaryProject if known>`
  - `cwd: <current cwd>`
  - `started: <current timestamp>`
  - `username: <current username>`
  - `hostname: <current hostname>`
  - `capture: deliberate`
  - `agent: claude-code`
  - `session_id: <exact host-provided session id>`, when available

New notes use `agent` and `session_id`, not `claude_session_id`. Existing notes
with the legacy field remain valid; do not rewrite them. Session identity is the
pair of agent and session ID, never a bare ID shared across hosts.

For the `coding` profile, write `note_type: coding_session` (frontmatter
`type: coding_session`) and use the same common frontmatter plus these
schema-required fields:

- `repository: <confirmed stable repository identifier>`
- `repo_root: <git rev-parse --show-toplevel>`
- `cwd: <current cwd>`
- `branch: <git rev-parse --abbrev-ref HEAD>`
- `git_sha: <git rev-parse HEAD>`

When the current branch has a pull request, also add the typed optional fields
`pull_request_number`, `pull_request_title`, `pull_request_url`, lowercase
`pull_request_state`, `pull_request_base`, and `pull_request_head`. Resolve the
pull request with a read-only GitHub query (e.g. `gh pr view --json ...`); omit
those fields when no PR exists. Write the number as a quoted string, for example
`pull_request_number: "123"`, so exact metadata queries behave consistently
across storage backends. Never infer or copy repository/PR identity only from
conversation text. Stop if the required coding fields cannot be proven.

Begin the body with `# <exact note title>`.

Use these sections, omitting optional ones that add no value:

- `## Summary`: one concrete sentence that does not merely repeat the title
- `## Story`: problem -> approach -> current state and impact in substantive prose
- `## Project Memory`, when the work surfaced a durable lesson future readers
  need — the constraint discovered, the boundary made explicit, the shortcut to
  avoid
- `## Changed Files`, when paths are useful for resuming
- `## Verification`, for checks actually run and their outcomes
- `## Observations`
- `## Relations`, when the session has an obvious graph target

Use observations to distill durable facts for structured recall rather than
duplicating every narrative sentence:

- `[result]` for concrete outcomes
- `[decision]` for each decision made or preserved
- `[blocker]` for each unresolved blocker
- `[next_step]` for the next concrete action; include at least one
- `[verification]` or `[changed_file]` only when the item is itself important
  project memory, not merely supporting detail

Do not create separate Decisions, Blockers, or Next Action sections with plain
bullets. Omit empty categories instead of writing placeholder text such as
"None."

Relations are not observations. Put them under `## Relations` using Basic
Memory relation syntax, for example `- relates_to [[Exact existing note title]]`.
Never write `[relates_to]` or a bare `memory://` URL as an observation. Only add
a relation when its target is an existing task, decision, spec, issue, or PR note.

## Confirm

Reply with the permalink and the one next action the checkpoint preserves.
