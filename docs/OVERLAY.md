# Upstream overlay architecture

The original Basic Memory repository (basicmachines-co/basic-memory) is read-only.
The daily GitHub Action checks out main from upstream, mirrors its selected files
unchanged to vendor/upstream for audit and reproducibility, and builds every
client artifact from the fresh upstream checkout, not from hand-edited copies.

Deployment-specific adaptations are declared in overlays/skills/<skill>/<target>.json
(or all.json). Each file contains a replacements list with old and new
literal strings. The generator composes the overlay in memory while building
claude/, openai/, and optional extras. Original upstream skill files and the
vendored snapshot are never modified by the overlay.

For safety, every old anchor must match exactly once. An unrelated upstream
edit does not require an updated SHA or manual rebase; an incompatible change
to an anchor fails the Action before publishing. On such a failure, update
only the relevant overlay after inspecting the upstream change. New upstream
skills are discovered automatically; dropping below the known minimum count
fails validation. The exclusions remain explicit in config/build.json.

GitHub Actions executes: upstream checkout -> immutable snapshot/lock ->
overlay build -> tests, digest and artifact checks -> direct commit to main.
Never run, import or execute upstream source as code; it is read as data.
The OpenAI artifacts intentionally contain no MCP server definition because
https://bm.xlap.pl/mcp is registered independently in ChatGPT.
