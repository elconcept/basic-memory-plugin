# Instalacja testowa (nieprodukcyjna)

To repo zawiera kandydatów `claude/` i `openai/` **wyłącznie do weryfikacji**. Dla Claude Code marketplace jest w `.claude-plugin/marketplace.json`, a dla Codex/ChatGPT Desktop w `.agents/plugins/marketplace.json`.

Oba warianty korzystają z tego samego hostowanego MCP: `https://bm.xlap.pl/mcp`; **nie** zawierają sekretów ani lokalnego serwera Basic Memory. OpenAI jest na razie pakowany wyłącznie w wariancie testowym M, opartym na standardowym `mcp.json` z deklaracją OAuth. Nie ma jeszcze dowodu, że autoryzacja/instalacja działa na docelowym koncie ChatGPT oraz w Codex.

**Braki blokujące wdrożenie produkcyjne:** brak zweryfikowanego T05 (hooki i kontrola checkpointów), brak smoke w prawdziwym Claude Code/Codex/ChatGPT/claude.ai, brak potwierdzenia transferu autoryzacji oraz pełnej recenzji licencji upstream. Nie należy oznaczać produktu jako gotowego ani czyścić istniejących połączeń.

Kopie skilli pochodzą z aktualizowanego przez PR upstreamu, modyfikacje są zakotwiczone w `patches/skills/` i budowanie zatrzymuje się przy zmianie kotwic. **Żaden merge upstreamu ani v1.2 nie jest automatyczny.**
