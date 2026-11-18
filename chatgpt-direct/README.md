# Direct Basic Memory workflows for ChatGPT

This directory defines eight **independently selectable, single-skill plugins** for ChatGPT. Each plugin reuses the one already connected Basic Memory application instead of creating another MCP connection.

| Plugin mention | Purpose |
| --- | --- |
| `@bm-orient` | Resume work from Basic Memory |
| `@bm-remember` | Save a short note |
| `@bm-decide` | Record a decision |
| `@bm-checkpoint` | Save a handoff checkpoint |
| `@bm-share` | Copy a note into an explicitly approved team project |
| `@bm-writing` | Edit or review a memory note |
| `@bm-status` | Read-only status report |
| `@bm-setup` | Configure and verify a Basic Memory project |

Every package contains one `skills/<name>/SKILL.md` plus `agents/openai.yaml`, `.app.json`, root `plugin.json`, and a legacy compatibility manifest. `bm-setup` also ships three schema references.

**Only one MCP connection:** Each `plugin.json` declares `extensions.com.openai.apps: './.app.json'`; `.app.json` references the existing `asdk_app_6afb2453a9748191a6865e06f09983f0` app. Do not add root `mcp.json`, legacy `.mcp.json`, `mcpServers`, local executors, or any second OAuth configuration to these packages.

Build with `python3 chatgpt-direct/package.py`. Eight independent archives are created in `chatgpt-direct/dist/`. Source changes in GitHub **do not automatically update** ChatGPT's private plugin releases; publish updates to each existing plugin with Plugin Creator and the current release ID. Never create duplicate entries to update an existing plugin.

These plugins were published as private app-backed ChatGPT plugin packages in November 2026. Account installation and `@` composer availability on chatgpt.com must be tested separately. The original Basic Memory app plugin currently retains its bundled skills as a fallback until web invocation of the eight individual plugins is confirmed.

Repository: https://github.com/elconcept/basic-memory-plugin
