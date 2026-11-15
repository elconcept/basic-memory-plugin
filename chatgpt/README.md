# Basic Memory (NAS): ChatGPT.com
This is the **ChatGPT.com cloud plugin source**, distinct from `openai/` (Codex) and `claude/`.

- Installed package identity: `basic-memory-nas`; version: `2.1.0`.
- Remote MCP: `https://bm.xlap.pl/mcp` with OAuth. No local MCP, hooks or credentials are bundled.
- The single ChatGPT router skill covers orient, remember, decide, checkpoint, share, status, setup and writing.
- `.github/workflows/publish-chatgpt.yml` packages the `chatgpt/` source and publishes immutable GitHub Release archives after relevant commits. **This is not an authenticated publication to ChatGPT.com.**
- Publish the ZIP to ChatGPT by calling Plugin Creator `update_plugin` against the existing exact backend plugin ID and expected current release ID. `create_plugin` is only for initial installation. Never invent an undocumented API token or endpoint.
- Existing ChatGPT plugin: `plugins_6af9d97a6be08191af5d1b25da11b434`. On each publication, read back the files and verify MCP authentication and a real read operation separately.
- Source manifest updates must also update the version (SemVer), package and README; preserve the plugin identity, server URL and audience.
- The original Codex and Claude builds are intentionally left untouched.
