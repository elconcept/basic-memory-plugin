# Plan wdrożenia: plugin `basic-memory-nas` (Claude + OpenAI)

Wersja planu: 1.2, 2026-11-09
Status: DO REALIZACJI W GRANICACH BRAMEK. Kierunek zatwierdzony przez recenzenta GPT. Uwagi R01–R13 ([recenzja GPT](REVIEW_GPT_2026-11-09.md)) i draft v1.2 GPT wprowadzone; odpowiedź z uzasadnieniem w [REVIEW_CLAUDE_2026-11-09.md](REVIEW_CLAUDE_2026-11-09.md). Ostatnie zatwierdzenie należy do użytkownika.
Repozytorium: `github.com/elconcept/basic-memory-plugin` (publiczne), gałąź robocza `impl/v1`
Upstream: `github.com/basicmachines-co/basic-memory`, gałąź `main`. Pin w `config/upstream.lock.json` (stan odniesienia: `b7d4006bd581c80c2bf4e4ca9a95f745ccee83a5`, 2026-11-08)
Serwer pamięci: `https://bm.xlap.pl/mcp` (Basic Memory 1.0.0 na Synology DS1821, kontener `basic-memory-server`, stack Portainera `mcp-basic-memory`), za Cloudflare Access

## Zmiany względem v1.1

| # | Zmiana | Źródło |
|---|---|---|
| V1 | Cel rozszerzony z „przeżyć kompakcję” na `recall → capture → consolidate`. Decyzje utrwalane w trakcie pracy upstreamowymi skillami; checkpoint jest siatką bezpieczeństwa, nie jedynym mechanizmem. | draft A1, R04, R07 |
| V2 | `saved` wyłącznie po weryfikacji przez hook (ta sama notatka, ten sam projekt, linia `checkpoint_key`) albo po `confirm` użytkownika z terminala. `mark` usunięty, deklaracja modelu daje najwyżej `reported_by_model`. | R01, R03 |
| V3 | Wpis bez projektu (`project: null`) nigdy nie jest ponawiany ani zapisywany przed jawnym `assign` na projekt z `allowedProjects`. | R02 |
| V4 | Materiał dzielony na części zamiast ucinania; sekcje „Decision candidates” i „Artifacts”; jawne `complete: false`. | R04 |
| V5 | Pole `capture` (ok/partial/failed:powód) i siatka `SessionStart(compact)` bez wpisu. | R05 |
| V6 | `SessionEnd` i odzyskiwanie sesji przerwanych bez kompakcji. | R07 |
| V7 | `PostToolUseFailure`. | R10 |
| V8 | Build per cel (`--target`), natywne `bm-*` osobno dla Claude i Codex, nadpisania i patche per cel. | R08, R09 |
| V9 | G4 bez `Config.Env` w ogóle; absolutna ścieżka CLI; diagnoza rozbieżności projektów CLI/MCP. | R06, K3, NAS_PRECHECK |
| V10 | G0-O z ośmioma osobnymi wynikami; §10 z testami OAuth od zewnątrz i kontrolą obejścia Cloudflare. | R11, R12 |
| V11 | Worker upstreamu: snapshot `vendor/upstream`, jeden PR `sync/upstream`, CI wyzwalane `workflow_dispatch` (PR bota nie uruchamia CI), issue przy awarii. | draft F, K1, K6 |
| V12 | Licencje: bez kodu pochodnego od części AGPL upstreamu; `NOTICE`. | K2 |
| V13 | Konserwacja wiedzy: cztery skille przez `cloudcli-cron` w holyclaude (bramka G7, faza F11), tylko do odczytu wymuszone konfiguracją. | draft A4/C, K5 |
| V14 | F10 rozszerzony: wariant z kompakcją (A), bez kompakcji (B), dwie kompakcje (C); raport etapowy. | R07, R13 |
| V15 | Jedna numeracja: fazy F, bramki G. Zadania T00–T10 z draftu zmapowane w §11.0. | K4 |

---

## 0. Instrukcje dla modelu wykonawczego

1. Wykonuj fazy w kolejności z §11. Kolejność F1 i F2 może się przeplatać; reszty nie przeskakuj.
2. Każda faza kończy się **kryterium akceptacji**. Bez spełnienia kryterium nie przechodzisz dalej.
3. Bramki weryfikacyjne (G0–G7) mają zdefiniowane wyniki. Wynik spoza opisanych wariantów oznacza **STOP i zgłoszenie** stanu faktycznego użytkownikowi. Niczego nie improwizuj.
4. Zakazy bezwzględne są w sekcji 12.
5. Pracuj na gałęzi `impl/v1`. Jeden commit na zakończone zadanie, message `<faza>: <co>`. Merge do `main`:
   - w punktach **[MERGE]**, po zielonym CI;
   - PR-y wyłącznie infrastrukturalne (`.github/`, `scripts/sync_upstream.py`, ich testy): po zielonym CI i zgodzie użytkownika.
6. Wynik każdej bramki zapisuj w `docs/VERIFICATION.md`: data, bramka, wynik, dowód. Postęp zadań w `docs/IMPLEMENTATION_LOG.md`. W dowodach nigdy nie umieszczaj wartości zmiennych środowiskowych, tokenów, nagłówków autoryzacji, ścieżek hosta NAS ani treści notatek z projektu `legal`.
7. Rozróżniaj stany dowodu: **SOURCE-VERIFIED** (jest w upstream@pin), **NAS-VERIFIED**, **CLIENT-VERIFIED** (na danej powierzchni), **SCHEDULED-VERIFIED** (zaplanowany przebieg z logiem), **GH-ACTIVE** (workflow na `main` z udanym przebiegiem). „Skonfigurowane” ≠ „działa”.

---

## 1. Cel i niezmienniki

**Cel:** jeden plugin, utrzymywany w jednym repozytorium, dostarcza skille Basic Memory, połączenie MCP do `bm.xlap.pl/mcp` i hooki ciągłości pamięci. Pamięć działa w cyklu:
- **recall:** orientacja na starcie (`bm-orient`, `memory-continue`);
- **capture:** utrwalanie decyzji w trakcie pracy (`bm-decide`, `bm-remember`, `memory-capture`) i checkpoint jako siatka bezpieczeństwa (kompakcja, koniec sesji, awaria);
- **consolidate:** zaplanowana higiena wiedzy w holyclaude (`memory-reflect`, `memory-curate`, `memory-defrag`, `memory-lifecycle`).

Podział odpowiedzialności: NAS (baza, graf, indeksy, schematy, MCP), plugin (dystrybucja skilli, routing projektu, hooki), holyclaude (zaplanowana konserwacja), GitHub Actions (synchronizacja upstreamu, CI).

| Powierzchnia | Jak dostaje plugin | Gdzie autoryzacja MCP |
|---|---|---|
| claude.ai (web), Claude Desktop (czat) | instalacja z marketplace'u GitHub w claude.ai | claude.ai (OAuth Cloudflare) |
| Claude Cowork | konto claude.ai | claude.ai |
| Claude Code (MacBook, holyclaude, sesje chmurowe) | synchronizacja z konta claude.ai | dziedziczona z claude.ai (G1) |
| chatgpt.com | mechanizm ustalony w G0-O | chatgpt.com (OAuth Cloudflare) |
| Codex (CLI/desktop, w tym holyclaude) | mechanizm ustalony w G0-O/G3 | dziedziczona z chatgpt.com (G0-O) |

**Niezmienniki:**

- **N1.** Autoryzacja MCP odbywa się wyłącznie w claude.ai i chatgpt.com. Claude Code, Codex i holyclaude nie przechodzą własnego OAuth i nie trzymają sekretów do `bm.xlap.pl`.
- **N2.** Żaden sekret nie trafia do repozytorium (także do historii git), manifestów, dziennika weryfikacji, PR, issue, logów CI ani **wyniku narzędzia widzianego przez model**.
- **N3.** Każdy skill Basic Memory występuje na danej powierzchni dokładnie raz. Nie ma zipów skilli, kopii w `~/.claude/skills` i `~/.agents/skills`, `npx skills add`, oficjalnych pluginów `basic-memory@basicmachines-co` ani `codex@basic-memory`.
- **N4.** Na danej powierzchni jest dokładnie jedno połączenie MCP do Basic Memory i dokładnie jeden zestaw narzędzi `bm_*`.
- **N5.** Hooki nie wykonują połączeń sieciowych i nie używają poświadczeń. Wolno im czytać lokalny transkrypt oraz zapisywać lokalny stan i materiał checkpointu (sekcja 7).
- **N6.** Stan `saved` powstaje **wyłącznie** na dwa sposoby: weryfikacja odpowiedzi MCP przez hook (`PostToolUse`, reguły 7.4) albo `confirm` wykonane przez użytkownika w terminalu. Deklaracja modelu nigdy nie daje `saved`. Każdy wpis inny niż `saved`/`dismissed` jest:
  - zgłaszany modelowi w tej samej sesji (`Stop`, jeden raz na wpis);
  - ponawiany w kolejnej sesji tego samego projektu (`SessionStart`);
  - widoczny w `bm-status`.

  Cicha utrata jest niedopuszczalna. Brak materiału lub błąd przechwycenia to jawny stan (`capture: failed:…`), nie cisza.
- **N7.** Zmiany z upstreamu trafiają wyłącznie przez PR z przeglądem. Brak auto-merge.
- **N8.** Projekt pamięci zawsze jawny: `primaryProject` z ustawień, a przy braku pytanie do użytkownika. Projektów `legal` i `main` nie wolno mieszać. Hook nigdy nie przyjmuje projektu domyślnego ani nie wywodzi go z bieżącej sesji. Wpis z `project: null` nie jest zapisywany ani ponawiany przed jawnym `assign`.
- **N9.** Niczego nie usuwasz z konfiguracji użytkownika bez uprzedniej kopii do `~/.bm-migration-backup/<YYYYmmdd-HHMMSS>/` z zachowaniem ścieżek względnych. Lista przeniesionych elementów trafia do VERIFICATION.md.
- **N10.** Do publicznego repo nie trafia kod pochodny od części upstreamu objętych AGPL-3.0 (`src/`, `scripts/`, `tests/`). Kopiowane są wyłącznie skille i pliki pluginów deklarowane jako MIT, z atrybucją w `NOTICE`.
- **N11.** Zaplanowane procesy (holyclaude) mają ograniczenia wymuszone konfiguracją uprawnień, nie tylko treścią promptu. Jeden przebieg = jeden jawny projekt. `legal` wyłącznie na osobne, wyraźne zlecenie użytkownika.

---

## 2. Ustalenia (stan faktyczny z poziomem pewności)

| # | Ustalenie | Źródło | Pewność |
|---|---|---|---|
| U1 | Upstream: 20 skilli `memory-*`, 8 `bm-*` dla Claude (`plugins/claude-code/skills/`) i 8 `bm-*` dla Codex (`plugins/codex/skills/`) | kod @b7d4006, `FEATURE_MATRIX.md` | pewne |
| U2 | `memory-ci-capture`: `metadata.internal: true` | kod | pewne |
| U3 | Upstreamowe hooki Claude i Codex uruchamiają `uv run --script` i piszą do lokalnego Basic Memory albo do Cloud `/proxy`. Self-hosted ma tylko `/proxy/projects`. | `plugins/*/hooks/hooks.json`, `api/app.py`, `mcp/async_client.py` | pewne |
| U4 | Upstreamowy PreCompact bez transkryptu nic nie zapisuje; z transkryptem tylko pierwszą prośbę i 3 ostatnie wypowiedzi użytkownika po 200 znaków | `cli/commands/hook.py` | pewne |
| U5 | Upstreamowy plugin Codex: `SessionStart` (`startup\|resume\|compact`) i `PreCompact` (`manual\|auto`); po kompakcji model pisze checkpoint skillem `bm-checkpoint` | `plugins/codex/hooks/hooks.json` | pewne |
| U6 | Claude Code: hook `mcp_tool` pomijany przy SessionStart na starcie sesji | dokumentacja hooków | pewne |
| U7 | Hooki Claude Code: `command` w formie exec (`command` + `args`) bez powłoki. SessionStart obsługuje źródło `compact` i `hookSpecificOutput.additionalContext`. | dokumentacja hooków | pewne |
| U8 | `PostToolUse` otrzymuje `tool_name`, `tool_input`, `tool_response`; `PostToolUseFailure` otrzymuje dane nieudanego wywołania; `SessionEnd` otrzymuje `reason`; `Stop` otrzymuje `stop_hook_active` i może zablokować turę (`decision: "block"`). Narzędzia MCP z pluginu mają nazwę `mcp__plugin_<plugin>_<serwer>__<narzędzie>`. | dokumentacja hooków | pewne co do mechanizmu; pola i nazwy narzędzi do zapisania jako fixture w G1 |
| U9 | Pluginy z claude.ai synchronizują się do Claude Code (≥ v2.1.273, logowanie kontem) | support.claude.com 13837440 | pewne |
| U10 | claude.ai: skille z pluginu działają w czacie, Desktopie i Cowork. Hooki działają tylko w Cowork i Claude Code. | support.claude.com 13837440 | pewne |
| U11 | Czy zdalny MCP z `.mcp.json` pluginu działa w czacie claude.ai i czy Claude Code dziedziczy autoryzację | brak dokumentacji | **G1** |
| U12 | OpenAI: format przenośny `plugin.json` + `mcp.json` + `skills/`; mapowanie na zarejestrowane połączenie przez `.app.json`; lokalne marketplace'y w ChatGPT Desktop i Codex | developers.openai.com/plugins | pewne co do mechanizmów |
| U13 | OpenAI: pełne, zapisywalne MCP opisane dla Business i Enterprise/Edu, ograniczone dla Pro. Synchronizacja ChatGPT → Codex nieudokumentowana. | help.openai.com, learn.chatgpt.com | **G0-O** |
| U14 | OpenAI: hooki pluginu nie działają w chmurowym ChatGPT Work. Instalacja przez web nie wdraża skryptów. W Codex hooki wymagają zatwierdzenia (trust). | learn.chatgpt.com/docs/plugins | pewne |
| U15 | Admin Tools ma `portainer_docker_proxy` (wywołanie Docker Engine API) z projekcją JMESPath `select`. Nie ma dedykowanego exec. | `portal_codemode_search`, instrukcje serwera Portainer | pewne; obsługa `select` dla `/containers/{id}/json` do potwierdzenia w G4 |
| U16 | `basic-memory doctor`: `--json`, `--skip-self-test`, `--project/-p` | `doctor.py` | pewne |
| U17 | Ręczne konektory `bm.xlap.pl` w claude.ai i ChatGPT usunięte przez użytkownika. Do F4 czat claude.ai nie ma dostępu do pamięci. | użytkownik | pewne |
| U18 | MacBook, Codex: włączony `codex@basic-memory` (MCP przez `uvx`) oraz wpis `mcp_servers.basic_memory` → `https://bm.xlap.pl/mcp` | wcześniejszy audyt | do potwierdzenia w F0 |
| U19 | Wszystkie 8 `bm-*` różni się między wariantem Claude i Codex (19–414 różniących się linii) | diff @b7d4006 | pewne |
| U20 | Licencje upstreamu: korzeń AGPL-3.0; `skills/README.md` oraz `plugin.json` obu pluginów deklarują MIT; brak osobnych plików `LICENSE` w tych katalogach | kod @b7d4006 | pewne |
| U21 | NAS: CLI tylko jako `/app/.venv/bin/basic-memory` (nie ma w `PATH` w `docker exec`), wersja 1.0.0; `project list --json` widzi **wyłącznie `main`**. Według użytkownika i wcześniejszego `bm_project` istnieją `main`, `legal`, `model-memory`. | `NAS_PRECHECK.md`, użytkownik | pewne co do obserwacji; przyczyna rozbieżności **G4** |
| U22 | GitHub: workflow `sync-upstream.yml` aktywny na `main` (GH-ACTIVE: ręczny przebieg OK); ochrona `main`: PR, wymagany `validate` (strict, także admin). PR otwarte przez `GITHUB_TOKEN` nie uruchamiają `pull_request`/`push`, więc PR #3 nie ma checku `validate`. | `gh`, `IMPLEMENTATION_LOG.md` | pewne |
| U23 | Holyclaude: `cloudcli-cron` v0.2.0 zainstalowany, 0 ledgerów. Obsługuje daily/weekdays/weekly/monthly, Run Now, Pause/Resume, Retry; bez własnej składni cron i bez „co 2 tygodnie”. | `HOLYCLAUDE_SCHEDULED_PROMPTS.md` | pewne co do instalacji; działanie **G7** |

---

## 3. Decyzje architektoniczne

- **D1.** Jedno repo, dwa artefakty generowane: `claude/` i `openai/`. Źródło upstreamu: snapshot `vendor/upstream/` utrzymywany przez worker (§9.2).
- **D2.** Nazwa pluginu `basic-memory-nas` na obu platformach. Klucz serwera MCP: `basic-memory`.
- **D3.** Skille na cel: 16 `memory-*` (wspólne źródło) + 8 natywnych `bm-*` (źródło właściwe dla celu: `plugins/claude-code/skills` albo `plugins/codex/skills`) = 24.
  - Wykluczone: `memory-ci-capture`, `memory-agents`, `memory-quest`, `memory-literary-analysis`.
  - Nadpisane (osobno na cel): `bm-setup`, `bm-status`, `memory-doctor`.
  - Spatchowane (osobno na cel): `bm-checkpoint`, `bm-orient`, `memory-okf`.
  - Nowy skill upstreamu nie jest ani cicho dodawany, ani cicho pomijany: zmiana liczby → build failuje, PR synchronizacji wymaga decyzji.
- **D4.** MCP przez plugin z OAuth Cloudflare.
  - Claude: `.mcp.json` z `type: http`, bez nagłówków.
  - OpenAI: wariant z G0-O.
  - Token serwisowy Cloudflare nie jest używany przez plugin.
- **D5. Potok checkpointu** (bez sieci w hookach):
  1. **Wyzwalacze przechwycenia** (lokalnie, materiał + wpis `pending`):
     - `PreCompact` (`trigger: manual|auto`);
     - `SessionEnd` (`trigger: session_end`), gdy od ostatniego wpisu tej sesji były ≥ `sessionEndMinTurns` wypowiedzi użytkownika;
     - `SessionStart` odzyskujący sesję przerwaną bez `SessionEnd` (`trigger: recovered`);
     - `SessionStart(compact)` bez wpisu dla tej kompakcji (`capture: failed:missing_precompact`, bez materiału).
  2. **`SessionStart`** wstrzykuje polecenie checkpointu (bieżąca sesja) albo ponowienia (inne sesje tego samego projektu).
  3. **Model** (skill `bm-checkpoint`, tryb hooka):
     - czyta wszystkie części materiału;
     - bez projektu: pyta użytkownika, wywołuje `assign`, dopiero potem pisze;
     - deduplikacja po `checkpoint_key`; istniejąca notatka → `bm_edit` (dopisanie), brak → `bm_write`;
     - odczyt kontrolny `bm_read` tej samej notatki.
  4. **`PostToolUse` / `PostToolUseFailure`** ustalają stan według reguł 7.4 (`written`, `saved`, `failed`).
  5. **`Stop`:** wpis tej sesji inny niż `saved`/`dismissed`/`reported_by_model` i `stop_hook_active == false` → jednorazowa blokada tury na wpis.
  6. **Retencja:** materiał usuwany 7 dni po `saved`/`dismissed`. Wpisy niezakończone nie są usuwane; po 30 dniach oznaczane `stale` i zgłaszane do decyzji użytkownika.
- **D6.** Wersjonowanie: wspólna wersja `1.0.N`, `N` rośnie przy zmianie zawartości generowanej. Pin upstreamu z `config/upstream.lock.json` trafia do `build-info.json`.
- **D7.** Repozytorium publiczne. Kod własny: MIT. Treści upstreamu: MIT z atrybucją (`NOTICE`), wyłącznie z katalogów deklarowanych jako MIT (N10).
- **D8.** Bieżące utrwalanie i konserwację realizują skille upstreamu, bez własnych odpowiedników. Jedyny własny kod wykonywalny w pluginie to `bm_hook.py`, bo upstreamowe hooki wymagają lokalnego Basic Memory (U3, N5).
- **D9.** Konserwacja wiedzy: `cloudcli-cron` w holyclaude (lokalny proces `claude`). Nie DSM, nie `/schedule`, nie `/loop`.

Odrzucone, nie wracać do nich: shim `/proxy`, SSH/`docker exec` z hooka, token serwisowy w hookach, `mcp_tool` na starcie sesji, automatyczny fallback na konektor konta, auto-merge, `saved` z deklaracji modelu, harmonogram DSM, lokalny Basic Memory na MacBooku.

---

## 4. Bramki weryfikacyjne

### G0. Sonda platform (F0, przed budową właściwego pluginu)

Cel: ustalić obsługiwane ścieżki **przed** inwestycją w build. Sonda to minimalne pluginy w gałęzi `probe`:
- `probe/claude/`: `plugin.json` (nazwa `bm-probe`), `.mcp.json` jak w 7.1, jeden skill `probe-ping` („call bm_project and report the list”);
- `probe/openai/`: `plugin.json` (format przenośny), jeden skill `probe-ping` i wariant MCP do testu.

**Claude (G0-C):**
1. W claude.ai dodaj marketplace z gałęzi `probe`. Jeśli UI nie pozwala wskazać gałęzi, użyj tymczasowego repo `elconcept/bm-probe` i usuń je po F0.
2. Zainstaluj `bm-probe`, połącz MCP.
3. Wykonaj G1.

**OpenAI (G0-O):**
1. Ustal typ konta ChatGPT (Plus/Pro/Business/Enterprise) i rolę (admin workspace'u czy nie).
2. Zarejestruj połączenie: chatgpt.com/plugins → „+” → „Add custom MCP server”, `https://bm.xlap.pl/mcp`, OAuth, „Create as a plugin”. Autoryzuj. Zapisz ID `plugin_asdk_app…`.
3. Sprawdź ścieżki dystrybucji `probe/openai`, w kolejności: (a) sync z GitHuba workspace'u (tylko admin); (b) marketplace lokalny w ChatGPT Desktop; (c) Plugin Creator.
4. Zapisz **osobno** każdy wynik, z dowodem (zrzut lub log, bez sekretów):

| Kod | Test | Wynik |
|---|---|---|
| O1 | `bm_project` w czacie ChatGPT | OK / brak / błąd |
| O2 | `bm_write` (`plugin-smoke-<data>`, projekt `main`, folder `tests`) | OK / tylko odczyt / błąd |
| O3 | `bm_read` tej notatki | OK / błąd |
| O4 | skill `probe-ping` widoczny w web | tak / nie |
| O5 | skill i narzędzia widoczne w Codex | tak / nie |
| O6 | O1–O5 po restarcie klienta | tak / nie |
| O7 | dokładnie jeden zestaw narzędzi Basic Memory (rejestracja + plugin z repo) | tak / duplikat do wyłączenia / duplikat nieusuwalny |
| O8 | Codex używa MCP bez `codex mcp login` | tak / nie |

Niedostępność funkcji w planie konta zapisz jako **ograniczenie platformy**, nie błąd serwera NAS.

**Wyniki G0-O:**
- **G0-O-R:** O1–O8 OK z mapowaniem `.app.json`. → Wariant R w 7.2.
- **G0-O-M:** O1–O8 OK tylko z przenośnym `mcp.json`. → Wariant M.
- **G0-O-X:** którykolwiek z O1–O3, O7 (nieusuwalny duplikat) lub O8 negatywny. → STOP, raport. Część OpenAI wstrzymana (`enabled_targets` bez `openai`), część Claude kontynuowana.

### G1. MCP z pluginu w claude.ai i dziedziczenie w Claude Code (w G0-C)

**Test:**
1. W czacie claude.ai: konektor pluginu widoczny, OAuth przechodzi, `bm_project` działa.
2. W Claude Code na MacBooku (logowanie kontem) po restarcie, w `/plugin` i `/mcp`: serwer pluginu *connected*, bez osobnego logowania.
3. Zapisz w VERIFICATION.md **dokładne nazwy narzędzi** (pełna lista `tools/list`, np. `mcp__plugin_bm-probe_basic-memory__bm_write`).
4. Zapisz jako fixture (`tests/fixtures/mcp/`, treść fikcyjna, struktura prawdziwa): wejście hooka `PostToolUse` dla `bm_write`, `bm_edit`, `bm_read` (sukces), `PostToolUseFailure` (błąd) oraz `SessionEnd`. Na tej podstawie ustalasz w 7.4 pola: identyfikator notatki w odpowiedzi zapisu, pole identyfikatora w wejściu odczytu, pole projektu.

**Wyniki:**
- **G1-A:** punkty 1–4 spełnione. → Kontynuuj.
- **G1-B, G1-C, G1-D** (Claude Code wymaga osobnego OAuth / brak serwera w czacie / dwa serwery): STOP. Raport do użytkownika. Bez fallbacku.

### G2. Instalacja docelowego pluginu OpenAI (F7)

Powtórzenie O1–O8 na docelowym pluginie ścieżką wybraną w G0-O. Wynik spoza G0-O-R/M → STOP.

### G3. Codex: hooki (F8)

**Test** (dla zainstalowanej wersji Codex, zapisz numer wersji): czy w pluginie działają `SessionStart(compact)`, `PreCompact`, `PostToolUse` dla narzędzi MCP, `Stop`, `SessionEnd`. Format wejścia i wyjścia ustal empirycznie, z fixture'ami jak w G1 pkt 4; `plugins/codex/hooks/*.py` (MIT) wolno czytać jako dokumentację formatu.

**Wyniki:**
- **G3-A:** wszystkie zdarzenia potrzebne do N6 (`PreCompact`, `SessionStart`, `PostToolUse` dla MCP) dostępne. → Pełny potok D5. Brak `Stop`/`SessionEnd` zapisz jako ograniczenie.
- **G3-B:** brak `PostToolUse` dla MCP. → Tryb ograniczony:
  - model po odczycie kontrolnym wywołuje `bm_hook.py report --key <ck> --ref <ref> [--error <txt>]`, co ustawia `reported_by_model` (nigdy `saved`);
  - `reported_by_model` jest widoczny w `bm-status` i w liczniku SessionStart; do `saved` przechodzi tylko przez `confirm` użytkownika po sprawdzeniu notatki;
  - ograniczenie zapisane w VERIFICATION.md;
  - test: fałszywy `report` (notatka nie istnieje) nie daje `saved`.
- **G3-C:** brak `PreCompact` lub `SessionStart`. → STOP dla hooków Codex; skille i MCP mogą działać bez hooków (decyzja użytkownika).

### G4. Diagnostyka na NAS przez `portainer_docker_proxy` (F3)

Wszystko tylko do odczytu. **Żadne wywołanie nie zwraca do modelu wartości zmiennych środowiskowych** (N2). W VERIFICATION.md wyłącznie nazwy zmiennych i ścieżki wewnątrz kontenera.
1. **Kontener:** GET `/containers/json`, `select` `[].{id:Id,name:Names[0],state:State,image:Image,ports:Ports}`. Znajdź `basic-memory-server`. Zapisz porty publikowane na hoście (wejście do §10 pkt 6).
2. **Konfiguracja:** GET `/containers/{id}/json` **wyłącznie** z `select` `{user:Config.User,cmd:Config.Cmd,entry:Config.Entrypoint,mounts:Mounts[].{d:Destination,rw:RW}}`. Pole `Config.Env` nie występuje w projekcji. Jeśli narzędzie nie obsługuje `select` dla tego endpointu → STOP, nie pobieraj pełnego inspect.
3. **Nazwy zmiennych:** exec `sh -c 'env | cut -d= -f1 | sort'` oraz `sh -c 'tr "\0" "\n" < /proc/1/environ | cut -d= -f1 | sort'` (tylko nazwy, proces exec i proces serwera).
4. **CLI:** exec `/app/.venv/bin/basic-memory --version` (POST `/containers/{id}/exec` z `{"Cmd":[...],"AttachStdout":true,"AttachStderr":true,"Tty":true}`, potem POST `/exec/{execId}/start` z `{"Detach":false,"Tty":true}`).
5. **Tożsamość środowiska:** exec `/app/.venv/bin/basic-memory project list --json` i porównanie z `bm_project` przez MCP. Przy rozbieżności (stan obecny, U21) diagnoza **tylko odczytem**:
   - `cat /proc/1/cmdline | tr "\0" " "` (polecenie serwera);
   - różnice nazw zmiennych między pkt 3a i 3b (np. `BASIC_MEMORY_HOME`, `BASIC_MEMORY_CONFIG_DIR`);
   - `ls -la` katalogu konfiguracji wskazanego przez te nazwy (same nazwy plików).
   Ustal, którą konfigurację czyta serwer, i powtórz pkt 5 z tą konfiguracją (np. `env BASIC_MEMORY_HOME=<ta sama ścieżka> …`). Żadnych zmian w plikach.
6. **Pliki:** exec `ls /app/data` (nazwy katalogów).

**Wyniki:**
- **G4-A:** pkt 4–6 OK i listy projektów zgodne (wprost albo po ustaleniu konfiguracji serwera w pkt 5). → `memory-doctor` w wariancie zdalnym, z dokładnym poleceniem exec zapisanym w VERIFICATION.md.
- **G4-B:** exec niedostępny albo nieczytelny. → Wariant „instrukcja ręczna”.
- **G4-C:** listy nadal niezgodne. → STOP. Raport do użytkownika. `memory-doctor` w wariancie G4-B do czasu wyjaśnienia. Nie zakładaj utraty projektów i nie diagnozuj indeksu.

### G5. Hooki w Cowork (F6)

1. SessionStart wstrzykuje polecenie orientacji.
2. Jeśli w Cowork da się wywołać kompakcję, przejdź pełny potok D5.
3. Sprawdź, czy `python3` jest dostępny w VM.

**Wyniki:** **G5-A** działa; **G5-B** hooki nie działają → ograniczenie platformy, nie blokuje wdrożenia.

### G6. Aktualizacja po zmianie w repo (F9)

Tabela: powierzchnia → czy się zaktualizowało → po jakim działaniu → **czy hooki nowej wersji się wykonują** → czy wymagane było ponowne zatwierdzenie zaufania (Codex). Dla Cowork uwzględnij anthropics/claude-code#65426 i zapisz procedurę obejścia. Sama widoczność nowej wersji nie zalicza bramki.

### G7. Holyclaude: zaplanowany proces z MCP (F11)

1. Plugin `cloudcli-cron` aktywny w CloudCLI UI (Settings → Plugins); sama obecność katalogu nie wystarcza. Strefa czasowa zweryfikowana.
2. Osobny workspace testowy z `.claude/settings.json`:
   - `basicMemory.primaryProject` jawnie;
   - `permissions.deny` dla narzędzi `bm_write`, `bm_edit`, `bm_move`, `bm_delete`, `bm_project_delete` (pełne nazwy z `claude_tool_prefix`) w fazie tylko do odczytu.
3. Prompt testowy tylko do odczytu, **Run Now**: nowy proces `claude` widzi `basic-memory-nas`, MCP *connected* bez interaktywnego logowania, `bm_project` i `bm_search` zwracają dane. Nie zakładaj, że nowy proces dziedziczy autoryzację otwartej sesji.
4. Test negatywny: prompt prosi o `bm_delete` notatki testowej → odmowa wynikająca z `permissions.deny`, notatka nienaruszona.
5. Historia wykonania: status `succeeded` zgodny z faktycznym wynikiem MCP. Sam kod wyjścia 0 nie wystarcza.

**Wyniki:**
- **G7-A:** pkt 1–5 spełnione. → F11.
- **G7-B:** nowy proces wymaga osobnego OAuth albo nie widzi pluginu → STOP, raport (bez obejść tokenem serwisowym, N1).
- **G7-C:** `permissions.deny` nie działa w procesie uruchamianym przez scheduler → STOP. Konserwacja wyłącznie ręczna.

---

## 5. Struktura repozytorium

```
basic-memory-plugin/
├── .claude-plugin/marketplace.json     # marketplace Claude → ./claude
├── .agents/plugins/marketplace.json    # marketplace OpenAI (repo) → ./openai
├── claude/                             # GENEROWANE
│   ├── .claude-plugin/plugin.json
│   ├── .mcp.json
│   ├── skills/<24>/
│   ├── hooks/{hooks.json,bm_hook.py}
│   ├── schemas/
│   ├── output-styles/
│   ├── LICENSE
│   └── UPSTREAM_ATTRIBUTION.md
├── openai/                             # GENEROWANE
│   ├── plugin.json
│   ├── .app.json | mcp.json            # wg G0-O
│   ├── skills/<24>/
│   ├── hooks/{hooks.json,bm_hook.py}
│   ├── LICENSE
│   └── UPSTREAM_ATTRIBUTION.md
├── vendor/upstream/                    # snapshot upstreamu (worker, tylko MIT-owe ścieżki + LICENSE)
├── src/
│   ├── hooks/bm_hook.py
│   └── templates/{claude,openai}/...
├── patches/skills/<skill>/{claude,openai,all}.json   # zakotwiczone zamiany old→new, przypięte do upstream_sha
├── config/{build.json,upstream.lock.json}
├── scripts/{build.py,check.py,sync_upstream.py}
├── tests/
│   ├── test_build.py
│   ├── test_bm_hook.py
│   ├── test_negative.py
│   ├── test_sync_upstream.py
│   └── fixtures/{transcripts,mcp}/     # syntetyczne, struktura z prawdziwych klientów
├── build-info.json
├── docs/{PLAN.md,VERIFICATION.md,IMPLEMENTATION_LOG.md,FEATURE_MATRIX.md,NAS_PRECHECK.md,HOLYCLAUDE_SCHEDULED_PROMPTS.md,REVIEW_*.md}
├── .gitleaks.toml
├── .github/workflows/{ci.yml,sync-upstream.yml}
├── LICENSE
├── NOTICE                              # podział licencji (U20) i atrybucja
└── README.md
```

---

## 6. Build

Tylko biblioteka standardowa Pythona 3.12. Testy w `unittest` (uruchamialne też przez `pytest`). Build **nie wykonuje** kodu upstreamu.

### 6.1. `config/build.json`

```json
{
  "plugin_name": "basic-memory-nas",
  "display_name": "Basic Memory (NAS)",
  "mcp_server_key": "basic-memory",
  "mcp_url": "https://bm.xlap.pl/mcp",
  "enabled_targets": ["claude"],
  "openai_variant": null,
  "openai_app_id": null,
  "claude_tool_prefix": null,
  "exclude_skills": ["memory-ci-capture", "memory-agents", "memory-quest", "memory-literary-analysis"],
  "overrides": ["bm-setup", "bm-status", "memory-doctor"],
  "patches": ["bm-checkpoint", "bm-orient", "memory-okf"],
  "expected_skill_count": { "claude": 24, "openai": 24 },
  "namespace_rewrites": {
    "basic-memory:bm-": "basic-memory-nas:bm-",
    "codex:bm-": "basic-memory-nas:bm-",
    "/basic-memory:": "/basic-memory-nas:"
  },
  "forbidden_strings": [
    "npx skills add",
    "bm install claude-code",
    "claude plugin marketplace add basicmachines-co",
    "cloud.basicmemory.com"
  ]
}
```

Wartości uzupełniane po bramkach:
- `enabled_targets`: `openai` dodawany dopiero po G0-O-R/M;
- `openai_variant` (`"R"`/`"M"`) i `openai_app_id` (nie jest sekretem): z G0-O;
- `claude_tool_prefix`: z G1, np. `mcp__plugin_basic-memory-nas_basic-memory__`.

Build celu z `enabled_targets`, dla którego wymagane pole ma `null`, kończy się błędem. Cel spoza `enabled_targets` może istnieć w repo jako **kandydat** (stan obecny: `openai/` w wariancie M, `dcfc611`) i jest sprawdzany `--check`, ale nie jest opisywany jako gotowy, a jego wpis w `.agents/plugins/marketplace.json` ma w opisie „candidate – not verified” do czasu G0-O.

### 6.2. `scripts/build.py`: algorytm

Wywołanie: `build.py --upstream vendor/upstream --out . --target claude|openai|all [--check]`. `all` = `enabled_targets`.

Dla każdego celu:
1. Źródła: `vendor/upstream/skills/memory-*/` (bez `evals/`) i natywne `bm-*` celu (`plugins/claude-code/skills/` dla `claude`, `plugins/codex/skills/` dla `openai`).
2. Odrzuć `exclude_skills` i skille z `metadata.internal: true` (własny parser frontmattera; nie importuj `validate_skills.py`, N10).
3. Modyfikacje skilli wyłącznie jako **zakotwiczone zamiany** z `patches/skills/<skill>/<cel>.json` albo `all.json` (stan zaimplementowany w `8f086a0`, `303fb45`): lista `{old, new}` przypięta do `upstream_sha`. Każde `old` musi wystąpić w upstreamowym pliku dokładnie raz; brak kotwicy, wielokrotne trafienie albo inny `upstream_sha` → exit 1 i ręczny przegląd w PR synchronizacji. Pełne przepisanie pliku dozwolone tylko jako jedna zamiana całej treści, z uzasadnieniem w PR.
4. Skill z listy `overrides`/`patches` w `build.json` bez pliku zamian dla celu → exit 1. W `build-info.json` zapisz SHA-256 upstreamowego `SKILL.md` każdego modyfikowanego skilla, per cel.
5. `namespace_rewrites` we wszystkich `*.md`.
6. `forbidden_strings`: trafienie → exit 1.
7. Wyczyść i wypełnij `<cel>/skills/`. Dla `claude` skopiuj `schemas/` i `output-styles/`.
8. Manifesty z szablonów (`{{version}}`, `{{plugin_name}}`, `{{display_name}}`, `{{mcp_url}}`, `{{mcp_server_key}}`, `{{claude_tool_prefix}}`, `{{openai_app_id}}`). Dla OpenAI **tylko** plik wariantu.
9. Skopiuj `src/hooks/bm_hook.py`, `LICENSE` i wygeneruj `UPSTREAM_ATTRIBUTION.md` (pin, ścieżki źródeł, podstawa MIT według U20: `skills/README.md`, `plugins/*/…/plugin.json`).
10. Wersja: hash zawartości bez pól wersji; przy zmianie `N+1`. `build-info.json`: `version`, `content_hash`, `upstream_sha` (z `config/upstream.lock.json`), `targets`, `override_upstream_hashes`, `skills` per cel.
11. Liczba skilli = `expected_skill_count[cel]`. Inaczej exit 1.
12. `--check`: build do katalogu tymczasowego i porównanie z repo. Różnica → exit 1.

### 6.3. `scripts/check.py`

1. Frontmatter wszystkich skilli (`name`, `description`, zgodność `name` z katalogiem), własna implementacja.
2. `claude plugin validate --strict ./claude` (gdy `claude` w `enabled_targets`).
3. OpenAI (gdy włączony): `plugin.json` i plik MCP względem schematów agent-plugins.org 1.0.0, a gdy nieosiągalne, strukturalnie wg 7.2.
4. Skan sekretów: `gitleaks` na plikach **i historii git** (`gitleaks git` w CI z `fetch-depth: 0`), konfiguracja `.gitleaks.toml`:
   - reguły: `[0-9a-f]{32}\.access`; `\b[0-9a-f]{64}\b`; `bmc_[A-Za-z0-9]{16,}`; JWT `eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}`; `-----BEGIN [A-Z ]*PRIVATE KEY-----`; `gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}`; `sk-[A-Za-z0-9]{20,}`;
   - `Authorization` i `Bearer` same w sobie nie są błędem;
   - allowlist wyłącznie: `build-info.json` (pola `*_hash`, `upstream_sha`), `config/upstream.lock.json` (`upstream_sha`, `snapshot_digest`), `tests/fixtures/` (wyłącznie oznaczone fikcyjne wartości).
5. Kontrole statyczne:
   - wynikowy `*/skills/memory-doctor/SKILL.md` nie zawiera `Config.Env` ani `/containers/{id}/json` bez `select` (R06);
   - żaden plik w `src/` nie zawiera nagłówka licencji AGPL ani fragmentów oznaczonych jako pochodzące z `src/basic_memory` (N10);
   - `bm_hook.py` nie importuje `socket`, `urllib`, `http`, `ssl`, `subprocess` (N5).
6. Testy (`python -m unittest`), w tym `tests/test_negative.py`:
   - wstrzyknięte `npx skills add` w zamianie → exit 1;
   - kotwica `old` nieobecna albo występująca wielokrotnie → exit 1;
   - przywrócony wykluczony skill → zła liczba skilli → exit 1;
   - fałszywy JWT w `claude/` → skan wykrywa;
   - brak pliku zamian dla jednego celu → exit 1;
   - `openai` w `enabled_targets` przy `openai_variant: null` → exit 1;
   - `Config.Env` w `memory-doctor` → exit 1.

---

## 7. Specyfikacja artefaktów

### 7.1. Plugin Claude

`plugin.json`:
```json
{
  "name": "{{plugin_name}}",
  "displayName": "{{display_name}}",
  "version": "{{version}}",
  "description": "Basic Memory (self-hosted, bm.xlap.pl): skills, MCP connection and credential-free continuity hooks.",
  "author": { "name": "elconcept" },
  "repository": "https://github.com/elconcept/basic-memory-plugin",
  "license": "MIT",
  "keywords": ["memory", "basic-memory", "mcp", "self-hosted"]
}
```
Bez katalogu `bin/`.

`.mcp.json`:
```json
{ "mcpServers": { "{{mcp_server_key}}": { "type": "http", "url": "{{mcp_url}}" } } }
```

`hooks.json`. Każdy handler: `"type": "command"`, `"command": "python3"`, `args` zaczyna się od `"${CLAUDE_PLUGIN_ROOT}/hooks/bm_hook.py"` (poniżej pominięte).

| Zdarzenie | Matcher | args (dalsza część) | timeout |
|---|---|---|---|
| SessionStart | `startup\|resume\|clear\|compact` | `session-start --harness claude` | 10 |
| PreCompact | (brak) | `pre-compact --harness claude` | 30 |
| PostToolUse | `{{claude_tool_prefix}}bm_(write\|edit\|read)` | `post-tool --harness claude` | 10 |
| PostToolUseFailure | `{{claude_tool_prefix}}bm_(write\|edit\|read)` | `post-tool-failure --harness claude` | 10 |
| PreToolUse | `Bash` | `guard --harness claude` | 5 |
| Stop | (brak) | `stop --harness claude` | 10 |
| SessionEnd | (brak) | `session-end --harness claude` | 30 |

`guard`: jeśli `tool_input.command` zawiera `bm_hook.py` i `confirm` → `permissionDecision: "deny"` z wyjaśnieniem. W każdym innym przypadku brak wyjścia.

`.claude-plugin/marketplace.json` (korzeń repo): marketplace `elconcept-basic-memory`, jeden plugin `basic-memory-nas`, `source: "./claude"`, bez `version` we wpisie.

### 7.2. Plugin OpenAI

`plugin.json` w formacie przenośnym (`$schema` agent-plugins.org 1.0.0) z `extensions.com.openai`:
- `interface`: `displayName`, `shortDescription`, `category`, `capabilities: ["Read","Write"]`;
- `hooks: "./hooks/hooks.json"`;
- w wariancie R: `apps: "./.app.json"`.

Dokładne nazwy pól sprawdź w dokumentacji przed pierwszym buildem. Rozbieżność → popraw szablon i odnotuj.

- **Wariant R:** `.app.json` mapuje na `{{openai_app_id}}`. Schemat z pliku wygenerowanego przez `@plugin-creator` w G0-O. Brak `mcp.json`.
- **Wariant M:** `mcp.json`:
  ```json
  {
    "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
    "mcpServers": {
      "{{mcp_server_key}}": {
        "type": "streamable-http",
        "url": "{{mcp_url}}",
        "extensions": { "com.openai": { "auth": { "type": "oauth", "client": { "mode": "dcr" } } } }
      }
    }
  }
  ```
  Brak `.app.json`.

`hooks/hooks.json` (Codex): zdarzenia z 7.1 w zakresie potwierdzonym w G3, w formacie wzorca `plugins/codex/hooks/hooks.json`. Polecenie: `python3 "${PLUGIN_ROOT}/hooks/bm_hook.py" <podkomenda> --harness codex`.

`.agents/plugins/marketplace.json` (repo): wpis `basic-memory-nas` → `./openai`.

### 7.3. `bm_hook.py`: interfejs

- Python 3, tylko stdlib, bez sieci (N5). Kod napisany samodzielnie; jako dokumentację formatu wolno czytać wyłącznie MIT-owe `plugins/*/hooks/*.py` i prawdziwe transkrypty (N10).
- Każda ścieżka kończy się `exit 0`. Wyjątki: celowa blokada w `stop` i odmowa w `guard`, wyrażone JSON-em, oraz `confirm`/`assign`/`report`/`dismiss`, które zwracają kod ≠ 0 przy odmowie.
- Podkomendy hooków (JSON na stdin): `session-start | pre-compact | post-tool | post-tool-failure | stop | session-end | guard`.
- Podkomendy ręczne: `status | assign | report | confirm | dismiss`.

**Konfiguracja.** Blok `basicMemory`, w kolejności rosnącego pierwszeństwa: `~/.claude/settings.json` (lub `$CLAUDE_CONFIG_DIR`), `<projekt>/.claude/settings.json`, `<projekt>/.claude/settings.local.json`. Dla Codex odpowiednik według dokumentacji ustawień Codex (ustalony w G3).

| Klucz | Domyślnie |
|---|---|
| `primaryProject` | **brak** (N8) |
| `allowedProjects` | **brak**; bez listy `assign` odmawia |
| `captureFolder` | `sessions` |
| `orientOnStart` | `true` |
| `checkpointOnCompact` | `true` |
| `checkpointOnSessionEnd` | `true` |
| `sessionEndMinTurns` | `3` |
| `materialMaxBytes` | `49152` (na część) |
| `materialMaxParts` | `4` |

**Katalog danych:** `$CLAUDE_PLUGIN_DATA` (Codex: `$PLUGIN_DATA`).
```
<DATA>/
  state.json               # wpisy checkpointów + open_sessions
  material/<ck>.<n>.md     # części materiału
  bm-hook.log              # dziennik JSONL, rotacja przy 1 MB
```
- Uprawnienia: katalogi `0700`, pliki `0600` (ustawiane jawnie).
- Zapis `state.json`: atomowy (plik tymczasowy, `fsync`, `os.replace`) pod `fcntl.flock` na `state.lock`. Uszkodzony `state.json` → przeniesienie do `state.json.corrupt-<ts>`, nowy stan, wpis w dzienniku i komunikat w najbliższym SessionStart (nie cicho).
- Brak zmiennej katalogu danych: ostrzeżenie na stderr i katalog zapasowy `~/.bm-hook-data/` z tymi samymi uprawnieniami.

**Wpis stanu:**
```json
{
  "ck": "ck-<16 hex>",
  "session_id": "...",
  "seq": 1,
  "trigger": "manual|auto|session_end|recovered",
  "harness": "claude",
  "project": "legal | null",
  "assigned_via": null,
  "capture_folder": "sessions",
  "status": "pending|written|saved|failed|reported_by_model|dismissed|stale",
  "capture": "ok|partial|failed:<powód>",
  "complete": true,
  "material": ["<DATA>/material/ck-....1.md"],
  "note_ref": null,
  "error": null,
  "created": "ISO8601",
  "updated": "ISO8601",
  "stop_blocked": false,
  "history": [{"at": "ISO8601", "from": "pending", "to": "written", "by": "post-tool"}]
}
```
`ck = "ck-" + sha256(f"{session_id}:{seq}")[:16]`, gdzie `seq` to liczba wcześniejszych wpisów tej sesji + 1.

`open_sessions`: `{session_id: {transcript_path, cwd, project, started, last_seen, ended: bool, last_capture_offset}}`.

Powody `capture: failed:…`: `no_transcript_path`, `unreadable`, `unknown_format` (niepusty plik, zero rozpoznanych wypowiedzi), `boundary_uncertain` (wtedy `partial`), `local_write_error`, `missing_precompact`.

### 7.4. `bm_hook.py`: logika podkomend

**`pre-compact`** (i wspólna funkcja przechwycenia dla `session-end` i odzyskiwania):
1. `checkpointOnCompact = false` → wpis do dziennika i koniec.
2. Projekt = `primaryProject` albo `null` (wtedy wpis wymaga `assign`; N8).
3. Brak `transcript_path`, plik nieczytelny lub nierozpoznany format → wpis `pending` z `capture: failed:<powód>`, bez materiału. Koniec. Nic nie jest „po cichu” udane.
4. Odczyt strumieniowy, linia po linii, z tolerancją uszkodzonych linii (liczba odrzuconych w nagłówku).
   - Segment: od ostatniej granicy kompakcji (znacznik ustalony w F1 na prawdziwym transkrypcie, zapisany jako fixture). Dla `session_end`/`recovered`: od `last_capture_offset`. Brak pewnej granicy → cały plik i `capture: partial` (`boundary_uncertain`).
   - Wypowiedzi użytkownika i asystenta (bez `isMeta`, bez wyników narzędzi) oraz wywołania narzędzi asystenta (nazwa + `file_path`, `path`, `command` do 200 znaków, `title`, `project`).
   - **Artifacts:** z wyników narzędzi wyłącznie identyfikatory pasujące do wzorców: SHA commitów z wyjścia `git commit`/`git log`, URL PR/issue GitHub, ścieżki plików z wywołań zapisu. Nigdy treść wyników.
5. Materiał markdown w częściach po `materialMaxBytes`, maks. `materialMaxParts`. Kolejność priorytetu przy przydziale budżetu:
   1. nagłówek: `ck`, `session_id`, `seq`, `trigger`, `cwd`, `project`, czas, `complete`, liczba pominiętych pozycji według rodzaju, liczba odrzuconych linii;
   2. **Decision candidates:** każdy akapit (użytkownika lub asystenta) z całego segmentu, który zawiera znacznik decyzji (PL/EN: `decyzj`, `zdecydow`, `ustal`, `postanow`, `wybier`, `przyjmuj`, `rekomend`, `decision`, `decided`, `we will`, `chose`, `agreed`, wzorce `\bD\d+\b`), do 1500 znaków, chronologicznie;
   3. Artifacts;
   4. wszystkie wypowiedzi użytkownika (do 2000 znaków każda);
   5. wszystkie wypowiedzi asystenta chronologicznie (do 2500 znaków każda; bloki kodu > 20 linii zastąpione znacznikiem `[code: n lines]`);
   6. lista wywołań narzędzi (deduplikowana, do 150).

   Przy braku miejsca pomijane są najpierw środkowe wypowiedzi asystenta z pkt 5, potem lista z pkt 6. Pkt 1–3 nie są obcinane, chyba że same przekraczają cały budżet (wtedy `complete: false` i dokładna liczba pominiętych). Każde pominięcie oznaczone `[OMITTED: n <rodzaj>]`.
6. Zapis części (`0600`) i wpisu `pending`. Dziennik: `checkpoint_required`. Błąd zapisu materiału → próba katalogu zapasowego; dalej błąd → wpis z `capture: failed:local_write_error`; błąd zapisu samego stanu → stderr i dziennik (pozostaje siatka `missing_precompact` z `session-start`).
7. Czas mierzony; cel < 5 s dla transkryptu 50 MB, przekroczenie → ostrzeżenie.

**`session-end`:** gdy `checkpointOnSessionEnd` i od `last_capture_offset` są ≥ `sessionEndMinTurns` wypowiedzi użytkownika → przechwycenie jak wyżej z `trigger: session_end`. Oznacz `open_sessions[sid].ended = true`.

**`session-start`** (wyjście: jeden `hookSpecificOutput.additionalContext`, bloki sklejone, łącznie ≤ 6000 znaków):
1. Rejestracja bieżącej sesji w `open_sessions`.
2. **Odzyskiwanie:** sesje z `open_sessions` z `ended == false`, `last_seen` > 2 h temu, których transkrypt istnieje i urósł od `last_capture_offset` o ≥ `sessionEndMinTurns` wypowiedzi → przechwycenie `trigger: recovered`.
3. **Retencja:** usuń materiał wpisów `saved`/`dismissed` starszych niż 7 dni; wpisy niezakończone > 30 dni → `stale`.
4. **Siatka kompakcji:** `source == compact` i brak wpisu tej sesji utworzonego w ostatnich 10 min → wpis `pending`, `capture: failed:missing_precompact`.
5. **Blok checkpointu:** `source == compact` i wpisy tej sesji `pending`/`failed` (`<TEKST_CHECKPOINT>`).
6. **Blok ponowień:** wpisy `pending|written|failed` z innych sesji, wyłącznie gdy `project == primaryProject` (oba niepuste). Maks. 5, najstarsze pierwsze (`<TEKST_RETRY>`).
7. **Blok nieprzypisanych:** wpisy z `project == null`, maks. 5: tylko lista (ck, data, cwd) i polecenie zapytania użytkownika (`<TEKST_UNASSIGNED>`). Nie zawiera ścieżek materiału.
8. **Licznik:** liczba wpisów niezakończonych w innych projektach, `reported_by_model` i `stale`, bez treści. Uszkodzony stan → komunikat.
9. **Blok orientacji:** `source in (startup, resume, clear)` i `orientOnStart` (`<TEKST_ORIENT>`).
10. Brak bloków → brak wyjścia.

**`post-tool`** (sukces wywołania):
- Dopasowanie wpisu: wzorzec `ck-[0-9a-f]{16}` w zserializowanym `tool_input` (zapis/edycja) albo `tool_input.<identyfikator>` równe `note_ref` wpisu (odczyt, edycja). Brak dopasowania → koniec.
- Błąd = `isError == true`, pusta treść albo treść, która według fixture'ów G1 oznacza błąd.
- `bm_write` / `bm_edit`:
  - `tool_input.project` ≠ `project` wpisu (albo wpis ma `null`) → bez zmiany stanu, `error: project_mismatch`, dziennik;
  - bez błędu → `written`, `note_ref` = identyfikator notatki z odpowiedzi (pole ustalone w G1; brak → `failed`, `error: no_ref`);
  - błąd → `failed`, `error` = pierwsze 300 znaków.
- `bm_read` → `saved` wyłącznie gdy jednocześnie: wpis `written`; znormalizowany identyfikator z `tool_input` == `note_ref`; `tool_input.project` == `project`; brak błędu; treść zawiera linię pasującą do `^checkpoint_key:\s*<ck>\s*$` (tryb wieloliniowy). W przeciwnym razie bez zmiany stanu i wpis w dzienniku z przyczyną (`readback_mismatch`, `readback_error`).
- Każda zmiana: wpis w `history` i w dzienniku.

**`post-tool-failure`:** dopasowanie jak wyżej; `bm_write`/`bm_edit` → `failed` z przyczyną; `bm_read` → bez zmiany stanu, `error: readback_failed`.

**`stop`:**
- `stop_hook_active == true` → brak wyjścia.
- Pierwszy wpis tej sesji o statusie `pending|written|failed` z `stop_blocked == false` → ustaw `stop_blocked = true`, wypisz `{"decision":"block","reason":"<TEKST_STOP>"}`.
- W przeciwnym razie brak wyjścia.

**`assign --key <ck> --project <p>`:** tylko dla wpisu z `project == null`; `p` musi należeć do `allowedProjects`. Ustawia `project`, `assigned_via: "assign"`. Skill wywołuje go **wyłącznie** po jawnej odpowiedzi użytkownika w bieżącej rozmowie.

**`report --key <ck> [--ref <ref>] [--error <txt>]`:** tylko tryb G3-B. Ustawia `reported_by_model` (z `--ref`) albo `failed` (z `--error`). Nigdy `saved`.

**`confirm --key <ck>`:** dla użytkownika w terminalu. Wypisuje wpis i wymaga przepisania `ck` z `/dev/tty`. Brak terminala sterującego → odmowa (kod 2). Ustawia `saved`, `history.by: "user-confirm"`.

**`dismiss --key <ck>`:** jak `confirm`, ustawia `dismissed` (świadoma rezygnacja użytkownika).

**`status`:** JSON z liczbą wpisów w każdym stanie, 10 ostatnimi wpisami (bez treści materiału) i liczbą `open_sessions`.

**Teksty** (angielskie, jak upstream; wartości podstawia skrypt):
- `<TEKST_CHECKPOINT>`: „Basic Memory checkpoint REQUIRED (context was just compacted). Before any other work, use `basic-memory-nas:bm-checkpoint` in hook mode with: checkpoint_key={ck}, material files={material or 'NONE – capture failed: {reason}; write the checkpoint from your current context and say so in the note'}, project={project or 'NOT SET'}, folder={capture_folder}. If project is NOT SET, ask the user which project to use, then run `bm_hook.py assign`; never assume. Read every material file in full. Report in one line: `Checkpoint saved: <note reference>` or `Checkpoint NOT saved: <reason>`.”
- `<TEKST_RETRY>`: „Basic Memory has {n} unfinished checkpoint(s) for project {project}: {lista: ck, status, trigger, data, material}. Tell the user in one line, then complete each with `basic-memory-nas:bm-checkpoint` in hook mode, unless the user says to skip (then ask them to run `bm_hook.py dismiss` in a terminal).”
- `<TEKST_UNASSIGNED>`: „{n} Basic Memory checkpoint(s) have no project: {lista: ck, data, cwd}. Ask the user which project each belongs to. Do not write them anywhere before the user answers and `bm_hook.py assign` succeeds.”
- `<TEKST_ORIENT>`: „Basic Memory (NAS) is available. Before the first substantive task, use `basic-memory-nas:bm-orient` for project {primaryProject}. If no project is configured, ask the user which project to use (never mix `legal` and `main`). During work, record decisions as they are made with `basic-memory-nas:bm-decide` and durable facts with `basic-memory-nas:bm-remember`. Keep it brief; if the tools are unavailable, say so in one sentence.”
- `<TEKST_STOP>`: „Basic Memory checkpoint {ck} is {status}. Finish it now with `basic-memory-nas:bm-checkpoint` in hook mode (write, then read back the same note), or tell the user explicitly: `Checkpoint NOT saved: <reason>`.”

### 7.5. Format notatki checkpointu

- Typ `session` (albo `coding_session` przy `sessionProfile: coding`), projekt `{project}`, folder `{capture_folder}`.
- Tytuł: `Checkpoint {YYYY-MM-DD HH:MM} {krótki temat}`.
- Frontmatter: `checkpoint_key: {ck}`, `session_id`, `seq`, `trigger`, `harness`, `capture`, `material_complete`, `status: active`.
- Treść **musi** zawierać osobną linię `checkpoint_key: {ck}`.
- Sekcje: Problem, Approach, Decisions (lista numerowana: decyzja, uzasadnienie, źródło: material/context), Changes, Artifacts (ścieżki, SHA, PR), Verification, Open questions / Blockers, Next action, Source material (`trigger`, `capture`, `complete`, liczba pominiętych).
- Każdy kandydat z „Decision candidates” trafia do Decisions albo do jawnej listy „Not decisions” (krótko). Pominięcie bez śladu jest błędem skilla.

---

## 8. Nadpisania i patche skilli

Treść po angielsku, jak upstream. Zmiany `bm-*` istnieją osobno dla `claude` i `openai`, bo wychodzą z różnych natywnych wariantów upstreamu (U19); zmiany `memory-*` mogą być wspólne (`all.json`).

Wszystkie modyfikacje z tej sekcji realizowane są zamianami zakotwiczonymi (6.2 pkt 3). Nazwy „nadpisanie” i „patch” oznaczają tylko zakres zmiany.

### 8.1. `bm-setup` (claude, openai)

1. `bm_project`. Brak narzędzi → plugin wymaga instalacji i autoryzacji w claude.ai/chatgpt.com. Koniec.
2. Wybór projektu z listy. **Bez domyślnego** (N8).
3. Zapis bloku `basicMemory` (`primaryProject`, `allowedProjects`, `captureFolder`, opcjonalnie `sessionProfile`/`repository`) do ustawień projektu albo globalnych, według wyboru użytkownika. W czacie tylko podanie ustawień.
4. Schematy `session`, `decision`, `task`, `coding_session` przez narzędzia MCP, według logiki upstreamu.
5. Opcjonalnie `outputStyle: basic-memory` (Claude).

Usunięte: instalacje, `bm install`, `npx skills add`, wybór local/cloud, `basic-memory hook status`.

### 8.2. `bm-status` (claude, openai)

Raport: projekt z ustawień; `bm_project`; 3 ostatnie checkpointy (`bm_search` po typie i folderze); liczba aktywnych zadań; **stan kolejki**: `python3 <plugin_root>/hooks/bm_hook.py status`, wyróżnione wpisy inne niż `saved`, osobno `reported_by_model`, nieprzypisane i `stale`, z instrukcją `confirm`/`dismiss`/`assign`. Bez powłoki (czat): wyjaśnienie, że kolejka istnieje tylko lokalnie.

### 8.3. `memory-doctor` (all)

Wariant według G4.

**G4-A:**
1. Sprawdź dostępność Admin Tools. Brak → podaj polecenie do ręcznego uruchomienia i zakończ.
2. Znajdź kontener: GET `/containers/json` z projekcją z G4 pkt 1.
3. Tożsamość środowiska: polecenie listy projektów zapisane w G4 (z absolutną ścieżką CLI i konfiguracją serwera) musi zgadzać się z `bm_project`. Rozbieżność → STOP.
4. Exec `/app/.venv/bin/basic-memory doctor --skip-self-test --json [--project X]` (z tą samą konfiguracją).
5. Raport **tylko do odczytu**. Nigdy nie pobieraj ani nie wyświetlaj `Config.Env`, pełnego inspect kontenera ani wartości zmiennych.
6. Naprawy (np. `reindex`) wyłącznie po wyraźnej zgodzie użytkownika, każde polecenie osobno.
7. Zakazane: usuwanie rekordów embeddingów, zmiana modelu embeddingów, `--self-test`, restart stacka.

**G4-B:** punkty 1–2 i 5–7 bez zmian, punkty 3–4 zastępuje instrukcja ręczna.

### 8.4. `bm-checkpoint` (claude, openai)

Sekcja „Hook mode”, gdy wywołanie zawiera `checkpoint_key`:
1. Przeczytaj w całości wszystkie pliki materiału. `NONE` → checkpoint z bieżącego kontekstu, zaznacz w Source material.
2. Projekt z polecenia. `NOT SET` → zapytaj użytkownika, wywołaj `bm_hook.py assign`, dopiero po sukcesie pisz.
3. Deduplikacja: `bm_search` po metadanych `checkpoint_key = {ck}` w projekcie (`memory-metadata-search`).
   - Istnieje → `bm_edit` w trybie dopisania (append), treść dopisku zawiera linię `checkpoint_key: {ck}`. Nigdy nadpisanie całej notatki.
   - Nie istnieje → `bm_write` według 7.5.
4. Odczyt kontrolny: `bm_read` **tej samej** notatki (identyfikator z odpowiedzi zapisu), z jawnym `project`.
5. Raport jednej linii: `Checkpoint saved: <ref>` albo `Checkpoint NOT saved: <reason>`. Sukcesu nie wolno ogłaszać bez udanego odczytu kontrolnego.
6. Tylko w trybie G3-B: `bm_hook.py report --key {ck} --ref <ref>`. Nigdy `confirm`.

Treść łączy materiał i bieżący kontekst. Wszystkie „Decision candidates” rozliczone według 7.5.

### 8.5. `bm-orient` (claude, openai)

Brak `primaryProject` → zapytaj użytkownika. Usuń odwołania do lokalnego CLI (`basic-memory hook status`). Na końcu orientacji: przypomnienie o `bm-decide`/`bm-remember` w trakcie pracy.

### 8.6. `memory-okf` (all)

Przy operacjach wymagających CLI: „On self-hosted Basic Memory the CLI runs only inside the server container; use the remote execution path of `basic-memory-nas:memory-doctor` or ask the user to run the command.”

---

## 9. CI i synchronizacja upstreamu

### 9.1. `ci.yml`

Wyzwalacze: `push` (`main`, `impl/v1`, `sync/**`), `pull_request`, `workflow_dispatch`. Uprawnienia: `contents: read`. Job `validate`:
1. Checkout z `fetch-depth: 0`.
2. Python 3.12; Node 22 i `@anthropic-ai/claude-code` (gdy `claude` w `enabled_targets`); `gitleaks`.
3. `python -m unittest discover -s tests`.
4. Gdy istnieje `scripts/build.py`: `python scripts/build.py --upstream vendor/upstream --out . --target all --check`.
5. Gdy istnieje `scripts/check.py`: `python scripts/check.py`.
6. gitleaks na historii.
7. Smoke test `sync_upstream.py` na przypiętym upstreamie (stan obecny, zachować).

Build i CI czytają wyłącznie `vendor/upstream` (bez pobierania upstreamu przy każdym przebiegu). Do czasu scalenia PR z pierwszym snapshotem krok 4 jest pomijany z komunikatem.

### 9.2. `sync-upstream.yml` (GH-ACTIVE)

Stan: działa na `main` (U22). Wyzwalacze: `schedule: "23 3 * * *"` i `workflow_dispatch`. `concurrency` bez anulowania. Uprawnienia: `contents: write`, `pull-requests: write`, **`actions: write`** (dla pkt 6). Kroki:
1. Checkout repo i upstream `main` (bez poświadczeń). Kod upstreamu nie jest wykonywany.
2. `sync_upstream.py` aktualizuje `vendor/upstream` i `config/upstream.lock.json` (tylko ścieżki z listy; symlinki, nieoczekiwane rozszerzenia i pliki > 2 MB → błąd).
3. Testy; gdy istnieje `build.py`: build `--target all` i `--check`, potem `check.py`. Po scaleniu F2 ten krok jest obowiązkowy (brak `build.py` = błąd).
4. Brak zmian → koniec bez PR.
5. Jeden PR z gałęzi `sync/upstream` (aktualizowany, nie mnożony), **draft**, etykieta `needs-review`. Opis: stary i nowy SHA, zmienione pliki, zmienione skille z liczbą linii, zmiany hashy nadpisanych skilli (ostrzeżenie), zmiany w `plugins/*/hooks/**`, manifestach i licencjach (ostrzeżenie), nowe lub usunięte skille (ostrzeżenie, build failuje do decyzji), status testów.
6. **Wyzwolenie CI:** `gh workflow run ci.yml --ref sync/upstream`. PR otwierany przez `GITHUB_TOKEN` nie uruchamia `pull_request`/`push`, więc bez tego kroku wymagany check `validate` nigdy nie powstaje (U22). Alternatywa: token GitHub App jako sekret repo (decyzja użytkownika).
7. Błąd w dowolnym kroku → issue „upstream sync failed” z linkiem do przebiegu (bez sekretów i bez treści logów z poświadczeniami); otwarte issue jest aktualizowane, nie mnożone.
8. **Brak auto-merge** (N7). Ochrona `main`: wymagany `validate`, ręczny merge.

`pull_request_target` zakazany.

---

## 10. Cloudflare Access (`bm.xlap.pl`)

Wykonawca sprawdza (odczyt przez Admin Tools i zapytania z zewnątrz bez poświadczeń) i raportuje. Zmiany wymagają zgody użytkownika. Wymagane:
1. Aplikacja Access z managed OAuth dla MCP i polityką Allow dla tożsamości użytkownika.
2. Dozwolone przekierowania OAuth, jeśli konfiguracja je ogranicza: callback claude.ai (adres z G0-C) i `https://chatgpt.com/connector_platform_oauth_redirect`.
3. DCR włączone.
4. Polityka Service Auth może pozostać dla innych klientów; plugin z niej nie korzysta.
5. Brak reguł `bypass`.
6. **Origin niedostępny z pominięciem Cloudflare:** port serwera MCP nie jest publikowany na interfejsie dostępnym spoza NAS (G4 pkt 1, `Ports`) albo jest ograniczony do sieci tunelu. Basic Memory sam nie uwierzytelnia, więc otwarty port = dostęp bez OAuth.

Testy z zewnątrz (wynik w VERIFICATION.md, bez tokenów):
- `POST /mcp` bez autoryzacji → `401` z `WWW-Authenticate` wskazującym metadane zasobu;
- `/.well-known/oauth-protected-resource` i `/.well-known/oauth-authorization-server` → poprawne metadane (issuer, endpointy, `registration_endpoint`);
- nagłówek z fałszywym i z wygasłym/nieprzeznaczonym tokenem → odrzucenie, brak listy narzędzi;
- poprawny klient (G1/G0-O) → narzędzia dostępne.

---

## 11. Fazy wdrożenia

### 11.0. Stan i mapowanie zadań z draftu

| Zadanie GPT | Faza v1.2 | Stan na 2026-11-09 |
|---|---|---|
| T00, T01 | F0 (dokumentacja, macierz funkcji) | zrobione (`d7e8557`, `3b232b9`) |
| T02, T03 | F0 (worker upstreamu, CI) | zrobione, GH-ACTIVE; **do poprawy §9.2 pkt 6–7** |
| T04 | F2 (+ część F3: zamiany zakotwiczone) | w toku: generator, `--target`, zamiany `bm-setup`/`bm-status`/`memory-doctor`, kandydaci `claude/` i `openai/`, marketplace'y (`a32b278`…`dcfc611`); brakuje `bm_hook.py`, zamian `bm-checkpoint`/`bm-orient`/`memory-okf` według 8.4–8.6, `NOTICE`, `check.py` |
| T05 | F1 | do zrobienia |
| T06 | F3 | do zrobienia |
| T07 | F4–F8 | do zrobienia |
| T08 | F11 | przygotowane prompty; G7 do zrobienia |
| T09 | G4 (F3) i F12 | preflight częściowy; G4 zatrzymane na U21 |
| T10 | F10 | do zrobienia |

### F0. Repo, audyt i sonda platform
1. Repo, `LICENSE`, `NOTICE`, `README.md`, `docs/VERIFICATION.md`, gałąź `impl/v1`, ochrona `main`. Worker i CI według §9 (w tym poprawki §9.2 pkt 6–7, jako PR infrastrukturalny).
2. **Audyt istniejących źródeł**, tylko odczyt, wynik w VERIFICATION.md (nazwy i ścieżki, nigdy wartości sekretów):
   - **MacBook, Claude Code:** `claude plugin list`; `/mcp`; nazwy w `~/.claude/skills`; wpisy `mcpServers` dotyczące Basic Memory w `~/.claude.json` i `~/.claude/settings.json`; `syncClaudeAiPlugins`.
   - **MacBook, Codex:** w `~/.codex/config.toml` sekcje `[mcp_servers.*]`, `[plugins.*]`, wpisy Basic Memory (U18); lista pluginów; `~/.agents/plugins/marketplace.json`; nazwy w `~/.agents/skills`.
   - **Holyclaude** (oba kontenery): to samo plus `~/.agents/` i konfiguracja `agents-sync`.
   - **claude.ai i ChatGPT:** konektory, pluginy, wgrane skille.
3. G0 (G0-C z G1, G0-O).
4. Uzupełnij `config/build.json` (`enabled_targets`, `openai_variant`, `openai_app_id`, `claude_tool_prefix`).

**Akceptacja:** audyt kompletny; G1-A; wynik G0-O zapisany (R, M albo X); `sync-upstream` z wyzwoleniem CI i issue przy awarii przetestowany ręcznym przebiegiem (PR #3 ma check `validate`).

### F1. Hook
1. Pobierz prawdziwe transkrypty z kompakcją: Claude Code (MacBook) i, jeśli dostępny, Codex. Ustal znacznik granicy kompakcji i format. **Nie commituj** transkryptów. Na ich wzór syntetyczne fixture'y z fikcyjną treścią i numerem wersji klienta.
2. Zaimplementuj `bm_hook.py` (7.3, 7.4), bez kodu pochodnego od AGPL (N10).
3. `tests/test_bm_hook.py`:
   - podział materiału, priorytety, `complete: false` i liczniki pominięć; decyzja z początku długiej sesji obecna w „Decision candidates” przy przepełnieniu budżetu;
   - granica kompakcji, dwie kolejne kompakcje w jednej sesji (różne `ck`, właściwe segmenty);
   - uszkodzone linie;
   - pięć awarii przechwycenia (`no_transcript_path`, `unreadable`, `unknown_format`, `local_write_error`, `boundary_uncertain`) i `missing_precompact` → wpis istnieje, brak cichego sukcesu;
   - przejścia `pending → written → saved`, `failed`, `PostToolUseFailure`;
   - **negatywne dla `saved`:** odczyt innej notatki zawierającej ten sam `ck` w tekście; odczyt w innym projekcie; `project_mismatch` przy zapisie; pusta odpowiedź; `isError`; `ck` tylko w środku linii (nie jako `checkpoint_key:`); `report` (G3-B) → `reported_by_model`, nigdy `saved`; `confirm` bez `/dev/tty` → odmowa;
   - **routing:** macierz `primaryProject` ∈ {`legal`, `main`, brak} × wpis ∈ {`legal`, `main`, `null`}: blok ponowień zawiera wyłącznie wpisy zgodne, `null` nigdy; `assign` spoza `allowedProjects` → odmowa;
   - `stop` blokuje raz na wpis i nie blokuje przy `stop_hook_active`;
   - `session-end` z progiem tur; odzyskiwanie sesji bez `SessionEnd`;
   - `guard` odrzuca `confirm` w Bash;
   - retencja i `stale`; uszkodzony `state.json`;
   - uprawnienia `0600`/`0700`;
   - współbieżność: dwa procesy, dwa jednoczesne checkpointy różnych sesji;
   - transkrypt 50 MB < 5 s (oznaczony `slow`).

**Akceptacja:** testy zielone.

### F2. Build
`build.py` (6.2), `check.py` (6.3), `test_build.py`, `test_negative.py`, `.gitleaks.toml`, `NOTICE`. Brakujące zamiany tymczasowo puste (kopia upstreamu). Scalenie PR snapshotu `sync/upstream` po przeglądzie (decyzja użytkownika), bo build wymaga `vendor/upstream`.

**Akceptacja:** testy zielone, w tym negatywne. `check.py` może jeszcze zgłaszać `forbidden_strings` w tymczasowym `bm-setup` (stan pośredni gałęzi, **bez merge**).

### F3. Skille i G4
Wykonaj G4. Napisz nadpisania (8.1–8.3) i patche (8.4–8.6) dla każdego celu z `enabled_targets`.

**Akceptacja:**
- `build.py --target all --check` i `check.py` zielone, 24 skille na cel;
- `claude plugin validate --strict` OK;
- G4 zapisana (G4-A albo G4-B; G4-C = STOP do decyzji użytkownika, nie blokuje reszty F3 przy wariancie G4-B `memory-doctor`).

**[MERGE]** `impl/v1` → `main`.

### F4. claude.ai
1. Usuń sondę `bm-probe`. Dodaj marketplace `elconcept/basic-memory-plugin`, zainstaluj `basic-memory-nas`, połącz MCP.
2. Czat webowy: `bm_project`; `bm_write` i `bm_read` notatki `plugin-smoke-<data>` (projekt `main`, folder `tests`), **identyfikator zapisany w VERIFICATION.md**; skille `basic-memory-nas:memory-notes` i `basic-memory-nas:bm-orient`.
3. Duplikaty (N3, N4): brak wgranych skilli Basic Memory; jeden konektor Basic Memory.
4. §10: testy z zewnątrz.

**Akceptacja:** punkty 2–4 spełnione.

### F5. Claude Code
Na MacBooku i w obu kontenerach holyclaude:
1. Wersja ≥ 2.1.273, logowanie kontem (`/status`). Klucz API → STOP dla hosta.
2. `syncClaudeAiPlugins` ≠ `false`.
3. **Czyszczenie z kopią (N9)** według audytu F0: `~/.claude/skills/{memory-*,bm-*}`, `~/.agents/skills/{memory-*,bm-*}`, wpisy MCP Basic Memory spoza pluginu, pluginy `basic-memory@basicmachines-co`. W `agents-sync` usuń linkowanie tych skilli. Każdy element do VERIFICATION.md.
4. Restart. `/plugin`: `basic-memory-nas` raz. `/mcp`: jeden serwer Basic Memory, *connected*. Nazwy narzędzi zgodne z `claude_tool_prefix`.
5. `primaryProject` i `allowedProjects` przez `/basic-memory-nas:bm-setup`: holyclaude-legal `legal`; główny holyclaude `main`; MacBook według użytkownika.
6. Test potoku D5 (MacBook): orientacja; praca; `/compact`; `status`: `pending` → `saved`; notatka zawiera `checkpoint_key`.
7. Testy awarii (MacBook, projekt testowy, nigdy `legal`):
   - nieistniejący projekt w `settings.local.json` → `failed`, jedna blokada `Stop`, `Checkpoint NOT saved`, blok ponowienia w kolejnej sesji; po przywróceniu `saved`;
   - brak `primaryProject` → blok nieprzypisanych, brak zapisu przed `assign`;
   - utrata OAuth (rozłączenie serwera w `/mcp`) → `failed`/`pending`, nie `saved`;
   - przerwanie procesu w trakcie zapisu (kill po `bm_write`, przed `bm_read`) → `written`, ponowienie w kolejnej sesji kończy się `saved` bez duplikatu notatki;
   - zamknięcie sesji bez kompakcji → wpis `session_end`; zabicie procesu → wpis `recovered` w kolejnej sesji;
   - błąd dysku (katalog danych tylko do odczytu) → komunikat, nie cisza.

**Akceptacja:** punkty 4, 6 i 7 na MacBooku; 4 i 6 na co najmniej jednym kontenerze.

### F6. Cowork i G5
Test skilli i MCP jak w F4 pkt 2, potem G5.

**Akceptacja:** skille i MCP działają; G5 zapisana.

### F7. ChatGPT i G2
(Tylko przy G0-O-R lub G0-O-M.) Usuń sondę; zainstaluj `basic-memory-nas` ścieżką z G0-O; G2 (O1–O8).

**Akceptacja:** O1–O8 spełnione.

### F8. Codex i G3
1. **Czyszczenie z kopią (N9):** wyłącz i odinstaluj `codex@basic-memory`; przenieś `[mcp_servers.basic_memory]` do kopii (pełna kopia `config.toml` przed edycją); usuń stare skille z `~/.agents/skills`.
2. Instalacja ścieżką z G0-O: marketplace osobisty (źródło git, `openai/`, `ref: main`); na holyclaude przez `~/.agents/` i `agents-sync`.
3. Zatwierdź hooki po przejrzeniu `hooks.json`.
4. G3, potem testy jak w F5 pkt 6–7 w zakresie dostępnych zdarzeń.
5. Dokładnie jeden zestaw `bm_*`.

**Akceptacja:** jeden zestaw `bm_*`, MCP bez `codex mcp login`, potok D5 zakończony `saved` (G3-A) albo `reported_by_model` + `confirm` użytkownika z udokumentowanym ograniczeniem (G3-B).

### F9. Aktualizacje i G6
1. `workflow_dispatch` dla `sync-upstream.yml`: przy braku zmian brak PR; przy zmianach PR z checkiem `validate`.
2. G6: sztuczna zmiana w `patches/skills/bm-status/claude.json` (komentarz w `new`), PR, merge, obserwacja na wszystkich powierzchniach, łącznie z wykonaniem hooków nowej wersji.

**Akceptacja:** tabela G6 kompletna.

### F10. Test ciągłości pamięci (kryterium odbioru)

Na MacBooku w Claude Code, potem w Codex (jeśli F8 zaliczone). Projekt `main`, folder `tests/continuity`. **Nie używaj projektu `legal`.** Każdy wariant w nowej, czystej sesji, z osobnym znacznikiem `CT-<data>-<wariant>`.

**Przebieg wspólny:** przeprowadź analizę testową (temat neutralny). Podejmij 6 decyzji `…-D1` … `…-D6`, każdą z krótkim uzasadnieniem. D1 i D2 podaje **asystent w pierwszych odpowiedziach** sesji (nie użytkownik), potem długi materiał, żeby znalazły się daleko od końca.

| Wariant | Zakończenie |
|---|---|
| **A** | `/compact`, potem zakończenie sesji |
| **B** | zakończenie sesji **bez** kompakcji (`/exit`) |
| **C** | dwie kompakcje (D1–D3 przed pierwszą, D4–D6 między pierwszą a drugą), potem zakończenie |

**Sprawdzenie:**
1. `bm_hook.py status`: zero wpisów niezakończonych dla tej sesji.
2. `bm_search` po znaczniku zwraca notatki zawierające wszystkie 6 znaczników z uzasadnieniami.
3. Nowy proces. Pytanie: „Jakie decyzje podjęliśmy w analizie CT-<data>-<wariant> i dlaczego?”. Model odtwarza je z Basic Memory, z odwołaniem do notatek.

**Kryterium:** w każdym wariancie 6/6 decyzji z poprawnym uzasadnieniem i odwołaniem do notatki. **5/6 lub mniej = niezaliczony odbiór.** Dla każdej brakującej decyzji raport etapowy w VERIFICATION.md: transkrypt → materiał (sekcja) → wywołanie MCP → notatka → odtworzenie; wskazany pierwszy etap, na którym zginęła.

**Sprzątanie:** usuń wyłącznie notatki, których identyfikatory zapisano w VERIFICATION.md podczas F4 i F10. Bez usuwania wzorcem ani całym folderem.

**Akceptacja całego wdrożenia:** F10 A, B i C zaliczone na Claude Code. Na Codex zaliczone albo ograniczenie z G3 udokumentowane.

### F11. Konserwacja wiedzy w holyclaude (po F5)

1. G7.
2. Cztery harmonogramy w `cloudcli-cron` (prompty w [HOLYCLAUDE_SCHEDULED_PROMPTS.md](HOLYCLAUDE_SCHEDULED_PROMPTS.md)), projekt `main`, workspace z `permissions.deny` z G7:

| Skill | Częstotliwość | Tryb w fazie 1 |
|---|---|---|
| `memory-reflect` | codziennie 02:20 | raport bez zapisu |
| `memory-curate` | co tydzień, pon. 02:45 | propozycje bez zapisu |
| `memory-lifecycle` | co tydzień, śr. 02:50 | propozycje bez zapisu |
| `memory-defrag` | co miesiąc, 1. dzień 03:10 | propozycje bez zapisu |

3. Faza 1 (tylko odczyt) trwa co najmniej 2 tygodnie. Przegląd raportów przez użytkownika.
4. Faza 2 (na osobną zgodę użytkownika): `memory-reflect` może zapisywać notatki w folderze `main/maintenance/` (zdjęcie `deny` tylko z `bm_write`). `bm_edit`, `bm_move`, `bm_delete` pozostają zablokowane; zmiany w istniejących notatkach wyłącznie ręcznie po akceptacji propozycji.
5. `legal`: osobny zestaw wyłącznie na wyraźne zlecenie użytkownika i po ocenie ryzyka.

**Akceptacja:** G7-A; cztery harmonogramy widoczne z kolejnymi terminami; `Run Now` z rzeczywistym odczytem MCP; pierwszy samodzielny przebieg każdego z nich z wynikiem w historii (SCHEDULED-VERIFIED).

### F12. Funkcje serwera (opcjonalnie, po odbiorze)

Benchmark wyszukiwania po polsku (20–50 zapytań na syntetycznym projekcie testowym: tekst/wektor/hybryda, trafność, czas), test importu małego dokumentu, `bm_schema` infer/validate/diff. Każda zmiana konfiguracji serwera wyłącznie po zgodzie użytkownika (§12 pkt 4).

### Wycofanie
- **claude.ai:** odinstaluj plugin i usuń marketplace. Przywrócenie ręcznego konektora wymaga decyzji użytkownika.
- **ChatGPT:** odinstaluj plugin. Połączenie z rejestracji może pozostać.
- **Hosty:** przywróć elementy z `~/.bm-migration-backup/<ts>/` według listy w VERIFICATION.md.
- **Holyclaude:** wstrzymaj (Pause) harmonogramy.
- **Repo:** `git revert` merge'a; plugin dostaje wersję `N+1` z poprzednią zawartością.

---

## 12. Zakazy dla wykonawcy

1. Żadnych sekretów w repo (w tym historii), manifestach, plikach MCP, skillach, PR, issue, logach CI ani VERIFICATION.md. Żadne wywołanie narzędzia nie może zwrócić modelowi wartości `Config.Env` ani nagłówków autoryzacji.
2. Bez oficjalnych pluginów Basic Memory (Claude i Codex), bez `bm install`, bez `npx skills add` i bez lokalnego `basic-memory` na klientach.
3. Bez zmian w Cloudflare (trasy, bypass, polityki) bez zgody użytkownika.
4. Bez modyfikacji kontenera, stacka i bazy na NAS. Wyjątki: odczyty i exec z G4 oraz naprawy `memory-doctor` zatwierdzone przez użytkownika.
5. Bez usuwania notatek poza tymi, których identyfikatory zapisano w VERIFICATION.md jako utworzone w tym wdrożeniu.
6. Bez ręcznej edycji `claude/`, `openai/` i `vendor/upstream/`.
7. Bez merge'a do `main` poza punktami [MERGE], PR-ami infrastrukturalnymi zatwierdzonymi przez użytkownika i PR-ami synchronizacji zatwierdzonymi przez użytkownika.
8. Bez usuwania czegokolwiek z konfiguracji hostów bez kopii (N9).
9. Bez commitowania prawdziwych transkryptów, materiałów checkpointów i treści notatek.
10. Bez kopiowania ani parafrazowania kodu z AGPL-owych części upstreamu (N10).
11. Bez wywoływania `bm_hook.py confirm`/`dismiss` przez model.
12. Bez użycia projektu `legal` w testach i harmonogramach (poza wyraźnym zleceniem użytkownika).
13. Wynik bramki spoza opisanych wariantów: STOP i zgłoszenie.

---

## 13. Rozstrzygnięcia

| Kwestia | Decyzja | Źródło |
|---|---|---|
| Fallback G1 na konektor konta | Brak automatycznego fallbacku. STOP i osobna decyzja. | v1.1 |
| Domyślny projekt | Brak. Jawny `primaryProject` albo pytanie; `null` nigdy nie ponawiany bez `assign`. | v1.1, R02 |
| `memory-literary-analysis` | Wykluczony. 24 skille na cel. | v1.1 |
| Sync upstreamu | Raz dziennie, jeden PR `sync/upstream`, draft, bez auto-merge, CI przez `workflow_dispatch` | v1.1, draft, K1 |
| `saved` w Codex bez `PostToolUse` | Najwyżej `reported_by_model`; `saved` tylko po `confirm` użytkownika | R01 |
| Scheduler konserwacji | `cloudcli-cron` w holyclaude; nie DSM, `/schedule`, `/loop` | draft, użytkownik |
| Częstotliwość `memory-defrag` | Raz w miesiącu, tylko propozycje | Claude (cotygodniowo to szum) |
| Licencja | Kod własny MIT; z upstreamu tylko części MIT z `NOTICE` | K2 |

**Pytania otwarte do użytkownika:**
1. U21: czy projekty `legal` i `model-memory` są obsługiwane przez ten sam kontener `basic-memory-server`, czy przez inną instancję? (Wpływa na G4 i na `allowedProjects`.)
2. §9.2 pkt 6: wyzwalanie CI przez `workflow_dispatch` (domyślnie) czy token GitHub App (wymaga utworzenia aplikacji i sekretu)?
3. F11 pkt 4: czy w ogóle dopuszczasz zapis przez zaplanowane procesy, czy konserwacja ma pozostać trwale w trybie raportów?

---

## Źródła

- Upstream `basicmachines-co/basic-memory` @b7d4006 (MIT): `skills/**`, `plugins/claude-code/**`, `plugins/codex/**` (w tym `hooks/hooks.json`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, README).
- Upstream (AGPL, tylko jako źródło faktów, bez kopiowania kodu): `src/basic_memory/api/app.py`, `src/basic_memory/mcp/async_client.py`, `src/basic_memory/cli/commands/hook.py`, `src/basic_memory/cli/commands/doctor.py`, `scripts/validate_skills.py`.
- Claude: support.claude.com/en/articles/13837440, support.claude.com/en/articles/11175166, code.claude.com/docs/en/plugins-reference, code.claude.com/docs/en/hooks
- OpenAI: developers.openai.com/plugins/build/plugins, developers.openai.com/plugins/deploy/submission, developers.openai.com/codex/mcp, learn.chatgpt.com/docs/plugins, help.openai.com/en/articles/12584461
- github.com/anthropics/claude-code/issues/65426
- github.com/grostim/cloudcli-cron
- To repo: `docs/REVIEW_GPT_2026-11-09.md`, `docs/REVIEW_CLAUDE_2026-11-09.md`, `docs/FEATURE_MATRIX.md`, `docs/NAS_PRECHECK.md`, `docs/HOLYCLAUDE_SCHEDULED_PROMPTS.md`, `docs/IMPLEMENTATION_LOG.md`
