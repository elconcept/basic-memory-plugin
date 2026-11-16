# Basic Memory (NAS): eight direct ChatGPT plugins

This directory contains **eight independently addressable ChatGPT plugins**. Each has one task-specific skill, a `plugin.json`, an OAuth-enabled `mcp.json`, and agent presentation metadata. `bm-setup` also bundles the Session, Decision and Task schema source notes.

| Explicit @ invocation | Workflow |
| --- | --- |
| `@bm-orient` | Read-only resume from notes, tasks, decisions and checkpoints |
| `@bm-remember` | Save one short note |
| `@bm-decide` | Record a typed decision |
| `@bm-checkpoint` | Create a resumable handoff |
| `@bm-share` | Copy a source note to a user-approved team project |
| `@bm-writing` | Apply the writing standard to a selected note |
| `@bm-status` | Read-only diagnostics |
| `@bm-setup` | Configure and validate the NAS project and schemas |

The shared remote server is `https://bm.xlap.pl/mcp` (OAuth DCR). No local Basic Memory server, local CLI, or client hooks are bundled. All eight skills disable implicit invocation, so explicitly selecting the named plugin is the intended path. The original `chatgpt/` router remains a fallback until the newly published plugins have been tested in the ChatGPT composer.

### Build and cloud publication

Run `python3 chatgpt-direct/package.py` to create one ZIP per plugin under `chatgpt-direct/dist/` (ignored/untracked output). Packages are independent; do not bundle all eight as one plugin.

The eight source packages were published to the owner's private ChatGPT plugins through Plugin Creator on 2026-11-16. **A GitHub push does not itself update their ChatGPT registrations.** Updating the cloud copies requires individually calling Plugin Creator `update_plugin` for each changed package, using its existing backend plugin ID and current release ID. Never use `create_plugin` for subsequent updates and never package OAuth credentials. Account UI installation, OAuth authorization and `@bm-*` composer recognition must be verified separately.
