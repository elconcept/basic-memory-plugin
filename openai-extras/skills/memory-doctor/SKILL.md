---
name: memory-doctor
description: "Check local Basic Memory projects with bm doctor, explain the findings, and run the suggested fixes once the user agrees. Use when search misses or repeats notes, or a save looks lost."
---

# Memory Doctor — remote NAS only

This deployment runs one Basic Memory 1.0.0 server on Synology. The Basic Memory CLI is **only** in the server container at `/app/.venv/bin/basic-memory`. Never install the CLI locally on a client; do not use the client's home directory as the knowledge base. Access to the server container requires an authorized admin tool and must project secrets out before the response reaches the model. Start with read-only diagnostics; any fix needs the user's prior approval and a backup. If remote admin access is absent, report that doctor cannot run rather than substituting a local process.

## When to Use

- Search misses a note the user knows exists, or returns the same note twice
- A note was saved but its file did not change, or the reverse
- The user asks whether Basic Memory is working, or to "check" or "fix" it
- After a crash, an interrupted import, or moving a project's folder

## Run It (only inside the authorized NAS container)

Use the admin connection to execute the following **inside `/basic-memory-server`**, never on a client machine:

```bash
/app/.venv/bin/basic-memory doctor --skip-self-test --json
```

First confirm `/app/.venv/bin/basic-memory --version` and `project list --json` and compare project identity with remote `bm_project(command="list")`. **If these disagree, STOP** — do not analyze or modify an index that may belong to a different configuration. For a single project add `--project <exact configured name>`. Do not fetch Docker `Config.Env` values into the model. This is a read-only check; the option without `--skip-self-test` can create disposable notes and must be separately authorized.

## Read the Report

```json
{
  "projects": [
    {
      "name": "work",
      "findings": [
        {
          "check": "search_index",
          "severity": "error",
          "summary": "1 search row does not match a current note, observation or relation.",
          "evidence": ["entity id=99, entity_id=99"],
          "action": {"kind": "reindex_search", "full": true},
          "command": "bm reindex --search --full --project work"
        }
      ],
      "has_errors": true
    }
  ],
  "skipped_cloud_projects": ["research"],
  "self_test": {"outcome": "skipped"},
  "has_errors": true
}
```

| Severity | Meaning | What to do |
|---|---|---|
| `error` | Will not go away without a fix | Offer the `command`; if it is null, explain the evidence |
| `warning` | Needs attention, may recover on its own | Offer the `command` if there is one |
| `info` | Expected while work is in progress | Mention it; a running server finishes it, and the `command` finishes it now |

Indexing catches up in the background. A duplicate, missing or extra search row
is a `warning` while file indexing is still running, because the pass may clear
it, and becomes an `error` once indexing has settled. If the report has only `info` findings, nothing is wrong. When no
Basic Memory server is running, nothing indexes in the background, so offer the
`command` on an `info` finding too.

Cloud projects are listed under `skipped_cloud_projects`: they are indexed on the
server, and local commands cannot fix them.

## Fix — approval required

Summarize precise findings, affected project, suggested commands, likely changes and risks. Preserve the diagnostic evidence while omitting secrets. No automatic reindex, schema migration, file replacement or deletion. After explicit user approval and a verified backup, run only the selected fix **inside the NAS container** with `/app/.venv/bin/basic-memory` and re-run the read-only doctor report to compare changes. If no admin access or backup is available, stop. Never infer absence of data from an incomplete CLI/MCP view.

## Exit Codes

`bm doctor` exits 0 when there are no errors and the self-test passed (or was
skipped), and 1 otherwise. Warnings and info never fail it.
