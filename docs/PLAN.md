# Plan wdrożenia: plugin `basic-memory-nas` (Claude + OpenAI)

Wersja planu: 1.1, 2026-11-09
Status: DO ZATWIERDZENIA (recenzent: GPT). Architektura i zakres zatwierdzone przez recenzenta w v1.0. Ta wersja wprowadza wymagane poprawki wykonawcze.
Repozytorium docelowe: `github.com/elconcept/basic-memory-plugin` (nowe)
Upstream: `github.com/basicmachines-co/basic-memory`, gałąź `main` (stan odniesienia: `b7d4006bd581c80c2bf4e4ca9a95f745ccee83a5`, 2026-11-08)
Serwer pamięci: `https://bm.xlap.pl/mcp` (Basic Memory 1.0 na Synology DS1821, stack Portainera `mcp-basic-memory`, ID 18), za Cloudflare Access

## Zmiany względem v1.0

| # | Zmiana | Powód (recenzja GPT) |
|---|---|---|
| C1 | Checkpoint zabezpiecza materiał **przed** kompakcją. PreCompact lokalnie wyciąga ograniczony materiał z transkryptu. Model zapisuje go przez MCP po kompakcji. | Pkt 1 |
| C2 | Maszyna stanów `pending → written → saved` / `failed`. Stan ustala hook `PostToolUse` na podstawie **faktycznej odpowiedzi MCP**, nie deklaracji modelu. Hook `Stop` blokuje zakończenie tury przy niezakończonym checkpoincie (jeden raz). Kolejka ponowień przy SessionStart. Klucz `checkpoint_key` zapobiega duplikatom. | Pkt 2 |
| C3 | Synchronizacja upstreamu raz dziennie, **zawsze PR**, bez auto-merge czegokolwiek | Pkt 3, pytanie 4 |
| C4 | Rozpoznanie możliwości claude.ai i OpenAI przeniesione do F0 (plugin sondujący) | Pkt 4 |
| C5 | Audyt i czyszczenie starych źródeł połączenia w Codex i Claude Code, zawsze z kopią zapasową | Pkt 5 |
| C6 | Prace na gałęzi `impl/v1`. `main` wyłącznie po pełnej walidacji. Testy negatywne w `pytest`. | Pkt 6 |
| C7 | Brak automatycznego fallbacku G1: przy niepowodzeniu STOP i decyzja użytkownika | Pytanie 1 |
| C8 | Brak domyślnego projektu: jawny `primaryProject`, a w razie braku pytanie | Pytanie 2 |
| C9 | Redakcja `Config.Env` w G4. Skan sekretów oparty na wzorcach poświadczeń i `gitleaks`. | Drobne |
| C10 | Kryterium odbioru: test ciągłości pamięci (F10) | Decyzja końcowa |

---

## 0. Instrukcje dla modelu wykonawczego

1. Wykonuj fazy w kolejności F0 → F10. Nie przeskakuj faz.
2. Każda faza kończy się **kryterium akceptacji**. Bez spełnienia kryterium nie przechodzisz dalej.
3. Bramki weryfikacyjne (G0–G6) mają zdefiniowane wyniki. Wynik spoza opisanych wariantów oznacza **STOP i zgłoszenie** stanu faktycznego użytkownikowi. Niczego nie improwizuj.
4. Zakazy bezwzględne są w sekcji 12.
5. Pracuj na gałęzi `impl/v1`. Commit message: `<faza>: <co>`. Merge do `main` wolno zrobić wyłącznie w punktach oznaczonych **[MERGE]**, po zielonym CI.
6. Wynik każdej bramki zapisuj w `docs/VERIFICATION.md`: data, bramka, wynik, dowód. W dowodach nigdy nie umieszczaj wartości zmiennych środowiskowych, tokenów, nagłówków autoryzacji ani treści notatek z projektu `legal`.

---

## 1. Cel i niezmienniki

**Cel:** jeden plugin, utrzymywany w jednym repozytorium, dostarcza skille Basic Memory, połączenie MCP do `bm.xlap.pl/mcp` i hooki ciągłości pamięci.

| Powierzchnia | Jak dostaje plugin | Gdzie autoryzacja MCP |
|---|---|---|
| claude.ai (web), Claude Desktop (czat) | instalacja z marketplace'u GitHub w claude.ai | claude.ai (OAuth Cloudflare) |
| Claude Cowork | konto claude.ai | claude.ai |
| Claude Code (MacBook, holyclaude, sesje chmurowe) | synchronizacja z konta claude.ai | dziedziczona z claude.ai (G1) |
| chatgpt.com | mechanizm ustalony w G0 | chatgpt.com (OAuth Cloudflare) |
| Codex (CLI/desktop, w tym holyclaude) | mechanizm ustalony w G0/G3 | dziedziczona z chatgpt.com (G3) |

**Niezmienniki:**

- **N1.** Autoryzacja MCP odbywa się wyłącznie w claude.ai i chatgpt.com. Claude Code, Codex i holyclaude nie przechodzą własnego OAuth i nie trzymają sekretów do `bm.xlap.pl`.
- **N2.** Żaden sekret nie trafia do repozytorium, manifestów, dziennika weryfikacji, PR ani issue.
- **N3.** Każdy skill Basic Memory występuje na danej powierzchni dokładnie raz. Nie ma zipów skilli, kopii w `~/.claude/skills` i `~/.agents/skills`, `npx skills add`, oficjalnych pluginów `basic-memory@basicmachines-co` ani `codex@basic-memory`.
- **N4.** Na danej powierzchni jest dokładnie jedno połączenie MCP do Basic Memory i dokładnie jeden zestaw narzędzi `bm_*`.
- **N5.** Hooki nie wykonują połączeń sieciowych i nie używają poświadczeń. Wolno im czytać lokalny transkrypt i zapisywać lokalny stan oraz materiał checkpointu, z ograniczeniami z sekcji 7.4.
- **N6.** Stan każdego wymaganego checkpointu jest ustalany na podstawie odpowiedzi MCP (`PostToolUse`). Checkpoint niezakończony (`pending`, `written`, `failed`) jest:
  - zgłaszany modelowi w tej samej sesji (`Stop`);
  - ponawiany w kolejnej sesji (`SessionStart`);
  - widoczny w `bm-status`.

  Cicha utrata jest niedopuszczalna.
- **N7.** Zmiany z upstreamu trafiają wyłącznie przez PR z przeglądem. Brak auto-merge.
- **N8.** Projekt pamięci zawsze jawny: `primaryProject` z ustawień, a przy braku pytanie do użytkownika. Projektów `legal` i `main` nie wolno mieszać. Hook nigdy nie przyjmuje projektu domyślnego.
- **N9.** Niczego nie usuwasz z konfiguracji użytkownika bez uprzedniej kopii do `~/.bm-migration-backup/<YYYYmmdd-HHMMSS>/` z zachowaniem ścieżek względnych. Lista przeniesionych elementów trafia do VERIFICATION.md.

---

## 2. Ustalenia (stan faktyczny z poziomem pewności)

| # | Ustalenie | Źródło | Pewność |
|---|---|---|---|
| U1 | Upstream: 20 skilli `memory-*` i 8 `bm-*` (`plugins/claude-code/skills/`) | kod | pewne |
| U2 | `memory-ci-capture`: `metadata.internal: true` | kod | pewne |
| U3 | Upstreamowe hooki Claude piszą do lokalnej bazy albo do Cloud `{cloud_host}/proxy`. Self-hosted ma tylko `/proxy/projects`. | `api/app.py`, `mcp/async_client.py` | pewne |
| U4 | Upstreamowy PreCompact bez transkryptu nic nie zapisuje. Wersja z transkryptem zapisuje tylko pierwszą prośbę i 3 ostatnie wypowiedzi użytkownika po 200 znaków. | `cli/commands/hook.py` | pewne |
| U5 | Upstreamowy plugin Codex: SessionStart(`compact`) wstrzykuje polecenie, model pisze checkpoint skillem `bm-checkpoint` | `plugins/codex/hooks/hooks.json` | pewne |
| U6 | Claude Code: hook `mcp_tool` pomijany przy SessionStart na starcie sesji | code.claude.com/docs/en/hooks | pewne |
| U7 | Hooki Claude Code: `command` w formie exec (`command` + `args`) bez powłoki. SessionStart obsługuje źródło `compact` i `hookSpecificOutput.additionalContext`. | dokumentacja hooków, potwierdzone przez recenzenta | pewne |
| U8 | `PostToolUse` otrzymuje `tool_name`, `tool_input` i `tool_response`. Narzędzia MCP z pluginu mają nazwę `mcp__plugin_<plugin>_<serwer>__<narzędzie>`. `Stop` otrzymuje `stop_hook_active` i może zablokować zakończenie tury (`decision: "block"`, `reason`). | dokumentacja hooków | pewne co do mechanizmu; faktyczne nazwy narzędzi do potwierdzenia w G1 |
| U9 | Pluginy z claude.ai synchronizują się do Claude Code (≥ v2.1.273, logowanie kontem, nie kluczem API) | support.claude.com 13837440 | pewne |
| U10 | claude.ai: skille z pluginu działają w czacie, Desktopie i Cowork. Hooki działają tylko w Cowork i Claude Code. | support.claude.com 13837440 | pewne |
| U11 | Czy zdalny MCP z `.mcp.json` pluginu działa w czacie claude.ai i czy Claude Code dziedziczy autoryzację | brak dokumentacji | **G1** |
| U12 | OpenAI: format przenośny `plugin.json` + `mcp.json` + `skills/`; mapowanie na zarejestrowane połączenie przez `.app.json` (ID `plugin_asdk_app…`); lokalne marketplace'y w ChatGPT Desktop i Codex | developers.openai.com/plugins/build/plugins | pewne co do mechanizmów |
| U13 | OpenAI: pełne, zapisywalne MCP opisane dla Business i Enterprise/Edu, ograniczone dla Pro. Synchronizacja ChatGPT → Codex nieudokumentowana. | help.openai.com, learn.chatgpt.com | **G0** |
| U14 | OpenAI: hooki pluginu nie działają w chmurowym ChatGPT Work. Instalacja przez web nie wdraża skryptów. W Codex hooki wymagają zatwierdzenia (trust). | learn.chatgpt.com/docs/plugins | pewne |
| U15 | Admin Tools ma `portainer_docker_proxy` (dowolne wywołanie Docker Engine API). Nie ma dedykowanego exec. | `portal_codemode_search`, 2026-11-09 | pewne |
| U16 | `basic-memory doctor`: `--json`, `--skip-self-test`, `--project/-p` | `doctor.py` | pewne |
| U17 | Ręczne konektory `bm.xlap.pl` w claude.ai i ChatGPT usunięte przez użytkownika. Do F0/F4 czat claude.ai nie ma dostępu do pamięci. | użytkownik | pewne |
| U18 | MacBook, Codex: włączony plugin `codex@basic-memory` (MCP przez `uvx`) oraz samodzielny wpis `mcp_servers.basic_memory` → `https://bm.xlap.pl/mcp` | wcześniejszy audyt recenzenta | do potwierdzenia w F0 (audyt) |

---

## 3. Decyzje architektoniczne

- **D1.** Jedno repo, dwa artefakty generowane: `claude/` i `openai/`.
- **D2.** Nazwa pluginu `basic-memory-nas` na obu platformach. Klucz serwera MCP: `basic-memory`.
- **D3.** 24 skille z 28.
  - Wykluczone: `memory-ci-capture`, `memory-agents`, `memory-quest`, `memory-literary-analysis`.
  - Nadpisane: `bm-setup`, `bm-status`, `memory-doctor`.
  - Spatchowane: `bm-checkpoint`, `bm-orient`, `memory-okf`.
- **D4.** MCP przez plugin z OAuth Cloudflare.
  - Claude: `.mcp.json` z `type: http`, bez nagłówków.
  - OpenAI: wariant z G0.
  - Token serwisowy Cloudflare nie jest używany przez plugin.
- **D5. Potok checkpointu** (bez sieci w hookach):
  1. **`PreCompact`:** hook odczytuje lokalny transkrypt od ostatniej granicy kompakcji. Zapisuje ograniczony materiał (sekcja 7.4) i wpis stanu `pending` z `checkpoint_key`.
  2. **`SessionStart(compact)`:** hook wstrzykuje polecenie obowiązkowego checkpointu ze ścieżką materiału i kluczem.
  3. **Model** (skill `bm-checkpoint`):
     - czyta materiał;
     - sprawdza, czy notatka z tym `checkpoint_key` już istnieje (deduplikacja);
     - zapisuje lub aktualizuje notatkę, łącząc materiał i skompaktowany kontekst;
     - wykonuje odczyt kontrolny.
  4. **`PostToolUse`:**
     - po `bm_write`/`bm_edit` z kluczem w treści: `written` przy odpowiedzi bez błędu, `failed` przy błędzie;
     - po `bm_read`, gdy odpowiedź zawiera klucz: `saved`.
  5. **`Stop`:** jeśli w tej sesji istnieje wpis inny niż `saved` i `stop_hook_active` jest fałszywe, hook blokuje zakończenie tury jeden raz z poleceniem dokończenia albo jawnego zgłoszenia niepowodzenia.
  6. **`SessionStart` (każde źródło):** wpisy inne niż `saved` z tego samego `primaryProject` trafiają do polecenia ponowienia.
  7. **Retencja:** materiał usuwany 7 dni po `saved`. Wpisy niezakończone nie są usuwane automatycznie. Po 30 dniach są zgłaszane jako `stale` przy każdym SessionStart, do decyzji użytkownika.
- **D6.** Wersjonowanie: wspólna wersja `1.0.N`, `N` rośnie przy zmianie zawartości generowanej. SHA upstreamu trafia do `build-info.json`.
- **D7.** Repozytorium publiczne (MIT plus atrybucja), bez sekretów.

Odrzucone, nie wracać do nich: shim `/proxy`, SSH/`docker exec` z hooka, token serwisowy w hookach, `mcp_tool` na starcie sesji, automatyczny fallback na konektor konta, auto-merge.

---

## 4. Bramki weryfikacyjne

### G0. Sonda platform (F0, przed budową właściwego pluginu)

Cel: ustalić obsługiwane ścieżki **przed** inwestycją w build. Sonda to minimalne pluginy w gałęzi `probe` tego samego repo:
- `probe/claude/`: `plugin.json` (nazwa `bm-probe`), `.mcp.json` jak w 7.1, jeden skill `probe-ping` („call bm_project and report the list”);
- `probe/openai/`: `plugin.json` (format przenośny), jeden skill `probe-ping` i wariant MCP do testu.

**Claude (G0-C):**
1. W claude.ai dodaj marketplace z gałęzi `probe`. Jeśli UI nie pozwala wskazać gałęzi, użyj tymczasowego repo `elconcept/bm-probe` i usuń je po F0.
2. Zainstaluj `bm-probe`, połącz MCP.
3. Wykonaj test G1 (niżej).

**OpenAI (G0-O):**
1. Ustal typ konta ChatGPT (Plus/Pro/Business/Enterprise) i rolę (admin workspace'u czy nie).
2. Zarejestruj połączenie: chatgpt.com/plugins → „+” → „Add custom MCP server”, `https://bm.xlap.pl/mcp`, OAuth, „Create as a plugin”. Autoryzuj. Zapisz ID `plugin_asdk_app…`.
3. W czacie ChatGPT wywołaj `bm_project`, potem `bm_write` (notatka `plugin-smoke-<data>` w projekcie `main`, folder `tests`) i `bm_read`. To test pełnego, zapisywalnego MCP.
4. Sprawdź, którą drogą `probe/openai` trafia do ChatGPT web, w kolejności:
   - (a) sync z GitHuba workspace'u (tylko admin);
   - (b) marketplace lokalny w ChatGPT Desktop (`~/.agents/plugins/marketplace.json`), sprawdzając, czy plugin widać też w web;
   - (c) Plugin Creator w ChatGPT.
   Zapisz, która działa i czy skill `probe-ping` jest widoczny w web.
5. **Kontrola duplikatów:** czy po instalacji `bm-probe` (z mapowaniem `.app.json` na ID z pkt 2) w ChatGPT są **dwa** aktywne zestawy narzędzi Basic Memory (plugin z rejestracji i plugin z repo). Jeśli tak, ustal, czy plugin z rejestracji da się ukryć lub wyłączyć bez zrywania połączenia, z którego korzysta mapowanie.
6. Codex na MacBooku (zalogowany kontem ChatGPT): czy `bm-probe` pojawia się sam. Jeśli nie, czy instalacja z marketplace'u osobistego (git) daje działające `bm_*` bez `codex mcp login`.

**Wyniki G0-O:**
- **G0-O-R:** mapowanie `.app.json` działa w web i Codex bez dodatkowej autoryzacji. Duplikat jest do wyłączenia albo nie występuje. → Wariant R w 7.2.
- **G0-O-M:** działa tylko przenośny `mcp.json` (sync workspace'u) i Codex dziedziczy autoryzację. → Wariant M.
- **G0-O-X:** pełne MCP nie działa na koncie, skille nie docierają do web albo każda ścieżka wymaga osobnego OAuth w Codex. → STOP. Raport do użytkownika. Część OpenAI wstrzymana, część Claude kontynuowana.

### G1. MCP z pluginu w claude.ai i dziedziczenie w Claude Code (wykonywana w G0-C)

**Test:**
1. W czacie claude.ai: konektor pluginu widoczny, OAuth przechodzi, `bm_project` działa.
2. W Claude Code na MacBooku (logowanie kontem) po restarcie, w `/plugin` i `/mcp`: serwer pluginu w stanie *connected*, bez osobnego logowania.
3. Odczytaj i zapisz w VERIFICATION.md **dokładne nazwy narzędzi**, np. `mcp__plugin_bm-probe_basic-memory__bm_write`. Potrzebne są do matcherów `PostToolUse` (po zmianie nazwy pluginu prefiks będzie `basic-memory-nas`).

**Wyniki:**
- **G1-A:** wszystkie trzy punkty spełnione. → Kontynuuj.
- **G1-B, G1-C, G1-D** (Claude Code wymaga osobnego OAuth / brak serwera w czacie / dwa serwery): STOP. Raport do użytkownika i GPT. Bez fallbacku (C7).

### G2. Instalacja docelowego pluginu OpenAI (F7)

Weryfikuje w docelowym pluginie ścieżkę wybraną w G0-O: narzędzia `bm_*`, skille, brak duplikatów. Wynik spoza G0-O-R/M → STOP.

### G3. Codex: hooki (F8)

**Test:**
- czy Codex obsługuje w pluginie `SessionStart` z `compact`, `PreCompact`, `PostToolUse` dla narzędzi MCP i `Stop` (dokumentacja hooków Codex plus test);
- format wejścia i wyjścia ustal z `upstream/src/basic_memory/hooks/adapters/codex.py`.

**Wyniki:**
- **G3-A:** wszystkie zdarzenia dostępne. → Pełny potok D5.
- **G3-B:** brak `PostToolUse` dla MCP albo `Stop`. → Tryb zastępczy:
  - skill `bm-checkpoint` po odczycie kontrolnym wywołuje `python3 <PLUGIN_ROOT>/hooks/bm_hook.py mark --key <ck> --status saved --ref <ref>` (albo `failed`);
  - SessionStart nadal ponawia wpisy niezakończone;
  - ograniczenie zapisane w VERIFICATION.md.

### G4. Diagnostyka na NAS przez `portainer_docker_proxy` (F3)

Wszystko tylko do odczytu. W VERIFICATION.md zapisuj wyłącznie nazwy zmiennych i zredagowane montowania (źródło → cel, tryb), **nigdy wartości**.
1. **Kontener:** GET `/containers/json`, projekcja `[].{id:Id,name:Names[0],state:State,image:Image}`. Znajdź kontener stacka `mcp-basic-memory`.
2. **Konfiguracja:** GET `/containers/{id}/json`, projekcja `{env:Config.Env,mounts:Mounts[].{s:Source,d:Destination,rw:RW},cmd:Config.Cmd}`. Lokalnie wyciągnij **tylko nazwy** zmiennych (`split('=')[0]`). Ustal katalog konfiguracji i bazy CLI (`BASIC_MEMORY_HOME`, `config.json`, ścieżka bazy) oraz montowanie `knowledge` (`/app/data`).
3. **Dostęp do CLI:** exec `basic-memory --version`:
   - POST `/containers/{id}/exec` z `{"Cmd":["basic-memory","--version"],"AttachStdout":true,"AttachStderr":true,"Tty":true}`;
   - POST `/exec/{execId}/start` z `{"Detach":false,"Tty":true}`.
4. **Dostęp do bazy:** exec `basic-memory project list --json`, albo równoważne polecenie listy projektów z `--help`. Lista projektów musi zgadzać się z `bm_project` przez MCP (`main`, `legal`, `model-memory`). To dowód, że CLI widzi bazę serwera, a nie nowe, puste środowisko.
5. **Dostęp do plików:** exec `ls /app/data` (same nazwy katalogów).

**Wyniki:**
- **G4-A:** punkty 3, 4 i 5 OK. → `memory-doctor` w wariancie zdalnym.
- **G4-B:** exec niedostępny albo nieczytelny. → Wariant „instrukcja ręczna”.
- **G4-C:** exec działa, ale lista projektów się nie zgadza. → STOP. Doctor diagnozowałby niewłaściwe środowisko.

### G5. Hooki w Cowork (F6)

**Test:**
1. SessionStart wstrzykuje polecenie orientacji.
2. Jeśli w Cowork da się wywołać kompakcję, przejdź pełny potok D5.
3. Sprawdź, czy `python3` jest dostępny w VM.

**Wyniki:**
- **G5-A:** działa.
- **G5-B:** hooki nie działają → ograniczenie platformy, nie blokuje wdrożenia.

### G6. Aktualizacja po zmianie w repo (F9)

Tabela: powierzchnia → czy się zaktualizowało → po jakim działaniu. Dla Cowork uwzględnij znany błąd anthropics/claude-code#65426 i zapisz procedurę obejścia.

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
│   ├── hooks/hooks.json
│   ├── hooks/bm_hook.py
│   ├── schemas/
│   ├── output-styles/
│   └── LICENSE
├── openai/                             # GENEROWANE
│   ├── plugin.json
│   ├── .app.json | mcp.json            # wg G0-O
│   ├── skills/<24>/
│   ├── hooks/hooks.json
│   ├── hooks/bm_hook.py
│   └── LICENSE
├── src/
│   ├── hooks/bm_hook.py
│   └── templates/{claude,openai}/...
├── overrides/skills/{bm-setup,bm-status,memory-doctor}/SKILL.md
├── patches/skills/{bm-checkpoint,bm-orient,memory-okf}.patch
├── config/build.json
├── scripts/{build.py,check.py}
├── tests/
│   ├── test_build.py
│   ├── test_bm_hook.py
│   ├── test_negative.py
│   └── fixtures/                       # syntetyczne transkrypty
├── build-info.json
├── docs/{PLAN.md,VERIFICATION.md}
├── .gitleaks.toml
├── .github/workflows/{ci.yml,sync-upstream.yml}
├── LICENSE
└── README.md
```

---

## 6. Build

Tylko biblioteka standardowa Pythona 3.12.

### 6.1. `config/build.json`

```json
{
  "plugin_name": "basic-memory-nas",
  "display_name": "Basic Memory (NAS)",
  "mcp_server_key": "basic-memory",
  "mcp_url": "https://bm.xlap.pl/mcp",
  "openai_variant": null,
  "openai_app_id": null,
  "claude_tool_prefix": null,
  "exclude_skills": ["memory-ci-capture", "memory-agents", "memory-quest", "memory-literary-analysis"],
  "overrides": ["bm-setup", "bm-status", "memory-doctor"],
  "expected_skill_count": 24,
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
- `openai_variant`: `"R"` albo `"M"`, z G0-O;
- `openai_app_id`: z G0-O, to nie jest sekret;
- `claude_tool_prefix`: z G1, np. `mcp__plugin_basic-memory-nas_basic-memory__`.

Build z wartością `null` w polu wymaganym dla danego artefaktu kończy się błędem.

### 6.2. `scripts/build.py`: algorytm

1. Zbierz źródła: `upstream/skills/memory-*/` (bez `evals/`) i `upstream/plugins/claude-code/skills/bm-*/`.
2. Odrzuć skille z `exclude_skills` oraz skille z `metadata.internal: true` (funkcja `is_internal_skill` z `upstream/scripts/validate_skills.py`).
3. Nadpisania z `overrides/`. W `build-info.json` zapisz SHA-256 upstreamowego `SKILL.md` każdego nadpisanego skilla (`override_upstream_hashes`).
4. Patche: `git apply --3way`. Konflikt → exit 1.
5. `namespace_rewrites` we wszystkich `*.md`.
6. `forbidden_strings`: trafienie → exit 1.
7. Wyczyść i wypełnij `claude/skills/` oraz `openai/skills/`. Skopiuj `schemas/` i `output-styles/` do `claude/`.
8. Manifesty z szablonów: podstaw `{{version}}`, `{{plugin_name}}`, `{{display_name}}`, `{{mcp_url}}`, `{{mcp_server_key}}`, `{{claude_tool_prefix}}`, `{{openai_app_id}}`. Dla OpenAI generuj **tylko** plik wariantu (`.app.json` albo `mcp.json`).
9. Skopiuj `src/hooks/bm_hook.py` do obu artefaktów.
10. Wersja: hash zawartości bez pól wersji. Przy zmianie `N+1` i ponowne wygenerowanie. Zapisz w `build-info.json`: `version`, `content_hash`, `upstream_sha`, `upstream_date`, `override_upstream_hashes`, `skills`.
11. Liczba skilli = `expected_skill_count` w obu artefaktach. Inaczej exit 1.
12. Tryb `--check`: buduje do katalogu tymczasowego i porównuje z repo. Różnica → exit 1.

### 6.3. `scripts/check.py`

1. Walidacja skilli: `upstream/scripts/validate_skills.py` na kopii `memory-*` oraz własna kontrola frontmatter `bm-*` (`name`, `description`).
2. `claude plugin validate --strict ./claude`.
3. Walidacja `openai/plugin.json` i pliku MCP względem schematów agent-plugins.org 1.0.0, a gdy są nieosiągalne, strukturalnie wg 7.2.
4. Skan sekretów:
   - `gitleaks detect --no-git --source . --config .gitleaks.toml`;
   - reguły własne w `.gitleaks.toml`:
     - `[0-9a-f]{32}\.access` (Cloudflare Access client ID);
     - `\b[0-9a-f]{64}\b` (sekret Access/hex);
     - `bmc_[A-Za-z0-9]{16,}`;
     - `eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}` (JWT);
     - `-----BEGIN [A-Z ]*PRIVATE KEY-----`;
     - `gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}`;
     - `sk-[A-Za-z0-9]{20,}`.
   - Słowa `Authorization` i `Bearer` **nie są** same w sobie błędem.
   - Allowlist wyłącznie dla `build-info.json` (pola `*_hash`, `upstream_sha`) i `tests/fixtures/`.
5. `pytest tests/`. Testy negatywne w `tests/test_negative.py`:
   - build z wstrzykniętym `npx skills add` w nadpisaniu → exit 1;
   - build z wykluczonym skillem przywróconym → zła liczba skilli → exit 1;
   - plik z fałszywym JWT w `claude/` → skan sekretów wykrywa;
   - konflikt patcha → exit 1.

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

`hooks.json`. Każdy handler ma `"type": "command"`, `"command": "python3"`, a `args` zaczyna się od `"${CLAUDE_PLUGIN_ROOT}/hooks/bm_hook.py"`. W liście `args` poniżej pominięto ten pierwszy element.

| Zdarzenie | Matcher | args (dalsza część) | timeout |
|---|---|---|---|
| SessionStart | `startup\|resume\|clear\|compact` | `session-start --harness claude` | 10 |
| PreCompact | (brak) | `pre-compact --harness claude` | 30 |
| PostToolUse | `{{claude_tool_prefix}}bm_(write\|edit\|read)` | `post-tool --harness claude` | 10 |
| Stop | (brak) | `stop --harness claude` | 10 |

`.claude-plugin/marketplace.json` (korzeń repo): marketplace `elconcept-basic-memory`, jeden plugin `basic-memory-nas`, `source: "./claude"`, bez `version` we wpisie.

### 7.2. Plugin OpenAI

`plugin.json` w formacie przenośnym (`$schema` agent-plugins.org 1.0.0) z `extensions.com.openai`:
- `interface`: `displayName`, `shortDescription`, `category`, `capabilities: ["Read","Write"]`;
- `hooks: "./hooks/hooks.json"`;
- w wariancie R: `apps: "./.app.json"`.

Dokładne nazwy pól sprawdź w dokumentacji przed pierwszym buildem. Rozbieżność → popraw szablon i odnotuj.

- **Wariant R:** `.app.json` mapuje na `{{openai_app_id}}`. Schemat weź z pliku wygenerowanego przez `@plugin-creator` w G0-O. Brak `mcp.json`.
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

`hooks/hooks.json` (Codex): te same zdarzenia co w 7.1, w zakresie potwierdzonym w G3, w formacie wzorca `upstream/plugins/codex/hooks/hooks.json`. Polecenie: `python3 "${PLUGIN_ROOT}/hooks/bm_hook.py" <zdarzenie> --harness codex`.

`.agents/plugins/marketplace.json` (repo): wpis `basic-memory-nas` → `./openai`. Kształt wpisu według dokumentacji OpenAI.

### 7.3. `bm_hook.py`: interfejs

- Python 3, tylko stdlib, bez sieci (N5).
- Każda ścieżka kończy się `exit 0`. Jedynym wyjątkiem jest celowa blokada w `stop`, wyrażona przez JSON, nie przez kod wyjścia.
- Podkomendy: `session-start | pre-compact | post-tool | stop | mark | status`. Wejście JSON na stdin, poza `mark` i `status`.

**Konfiguracja.** Blok `basicMemory` w kolejności rosnącego pierwszeństwa:
1. `~/.claude/settings.json` (lub `$CLAUDE_CONFIG_DIR/settings.json`);
2. `<projekt>/.claude/settings.json`;
3. `<projekt>/.claude/settings.local.json`.

Dla Codex wzorzec to `load_codex_settings` w upstreamowym `hook.py`.

| Klucz | Domyślnie |
|---|---|
| `primaryProject` | **brak**. Hook nie przyjmuje wartości domyślnej (N8). |
| `captureFolder` | `sessions` |
| `orientOnStart` | `true` |
| `checkpointOnCompact` | `true` |
| `materialMaxBytes` | `49152` |

**Katalog danych:** `$CLAUDE_PLUGIN_DATA` (Codex: `$PLUGIN_DATA`). Struktura:
```
<DATA>/
  state.json               # kolejka checkpointów
  material/<ck>.md         # materiał checkpointu
  bm-hook.log              # dziennik JSONL, rotacja przy 1 MB
```
- Uprawnienia: katalogi `0700`, pliki `0600` (ustawiaj jawnie po utworzeniu).
- Zapis `state.json`: atomowy (plik tymczasowy, `fsync`, `os.replace`) pod blokadą `fcntl.flock` na `state.lock`.
- Brak zmiennej katalogu danych:
  - `pre-compact` wypisuje na stderr ostrzeżenie i zapisuje materiał do `~/.bm-hook-data/` z tymi samymi uprawnieniami;
  - pozostałe podkomendy używają tego samego katalogu zapasowego.

**Wpis stanu:**
```json
{
  "ck": "ck-<16 hex>",
  "session_id": "...",
  "compaction_index": 1,
  "harness": "claude",
  "project": "legal",
  "capture_folder": "sessions",
  "status": "pending|written|saved|failed|stale",
  "material": "<DATA>/material/ck-....md",
  "note_ref": null,
  "error": null,
  "created": "ISO8601",
  "updated": "ISO8601",
  "stop_blocked": false
}
```
`ck = "ck-" + sha256(f"{session_id}:{compaction_index}")[:16]`, gdzie `compaction_index` to liczba wcześniejszych wpisów tej sesji powiększona o 1.

### 7.4. `bm_hook.py`: logika podkomend

**`pre-compact`:**
1. Jeśli `checkpointOnCompact = false`: tylko wpis do dziennika i koniec.
2. Jeśli brak `primaryProject`: utwórz wpis z `project: null`, status `pending`. Materiał zapisz normalnie. Model zapyta o projekt przy SessionStart.
3. Odczytaj `transcript_path` strumieniowo, linia po linii, z tolerancją uszkodzonych linii.
   - Wyznacz segment od **ostatniej granicy kompakcji**. Znacznik granicy ustal na prawdziwym transkrypcie Claude Code w F1: wpis z `isCompactSummary` albo `type: "system"` z podtypem kompakcji. Zapisz go w testach jako fixture syntetyczny. Brak granicy oznacza cały plik.
   - Parsowanie ról i treści wzoruj na `_transcript_turns` z upstreamowego `hook.py`: pomijaj `isMeta` i `toolUseResult`. Dodatkowo zbieraj **wywołania narzędzi** asystenta: nazwa plus pola `file_path`, `path`, `command` (do 200 znaków), `title`, `project`. Pomijaj wyniki narzędzi.
4. Złóż materiał markdown w limicie `materialMaxBytes`, w kolejności priorytetu:
   1. nagłówek z metadanymi: `ck`, `session_id`, `compaction_index`, `trigger`, `cwd`, `project`, czas;
   2. pierwsza wypowiedź użytkownika w segmencie (do 4000 znaków);
   3. **wszystkie** wypowiedzi użytkownika w segmencie (każda do 2000 znaków), od najnowszych, dopóki starcza limitu, potem prezentowane chronologicznie;
   4. ostatnie 15 wypowiedzi asystenta (każda do 2500 znaków);
   5. lista wywołań narzędzi (deduplikowana, do 150 pozycji);
   6. starsze wypowiedzi asystenta, dopóki starcza limitu.

   Dodaj znacznik „[TRUNCATED: n items omitted]” tam, gdzie coś pominięto.
5. Zapisz `material/<ck>.md` (`0600`) i wpis `pending`. Dziennik: `checkpoint_required`.
6. Czas wykonania mierz i zapisuj w dzienniku. Cel < 5 s dla transkryptu 50 MB. Jeśli przekroczony, zapisz ostrzeżenie (nie przerywaj).

**`session-start`** (wyjście: jeden obiekt `hookSpecificOutput.additionalContext`, wszystkie bloki sklejone):
1. **Retencja:**
   - usuń materiały wpisów `saved` starszych niż 7 dni;
   - wpisy niezakończone starsze niż 30 dni oznacz jako `stale` (bez usuwania materiału).
2. **Blok checkpointu,** gdy `source == compact` i istnieją wpisy `pending`/`failed` tej sesji (`<TEKST_CHECKPOINT>`).
3. **Blok ponowień:** wpisy `pending|written|failed|stale` z innych sesji, gdy `project == primaryProject` albo `project == null`. Maksymalnie 5, najstarsze pierwsze (`<TEKST_RETRY>`).
4. **Blok orientacji,** gdy `source in (startup, resume, clear)` i `orientOnStart` (`<TEKST_ORIENT>`).
5. Brak bloków → brak wyjścia.

**`post-tool`:**
- Wejście: `tool_name`, `tool_input`, `tool_response`. Szukaj wzorca `ck-[0-9a-f]{16}` w zserializowanym `tool_input` (dla zapisu) albo w tekście `tool_response` (dla odczytu). Brak klucza → koniec.
- Błąd to `tool_response.isError == true` albo brak treści.
- `bm_write` / `bm_edit`:
  - bez błędu → `written`, `note_ref` = pierwszy z napotkanych identyfikatorów w odpowiedzi (permalink, `file_path`, `title`, `external_id`);
  - błąd → `failed`, `error` = pierwsze 300 znaków.
- `bm_read`: odpowiedź bez błędu, zawierająca `ck`, przy wpisie `written` lub `failed` → `saved`.
- Każda zmiana trafia do dziennika.

**`stop`:**
- Jeśli `stop_hook_active == true` → brak wyjścia (zapobieganie pętli).
- Jeśli istnieje wpis tej sesji ze statusem innym niż `saved` i `stop_blocked == false`:
  - ustaw `stop_blocked = true`;
  - wypisz `{"decision":"block","reason":"<TEKST_STOP>"}`.
- W przeciwnym razie brak wyjścia.

**`mark --key <ck> --status saved|failed [--ref <ref>] [--error <txt>]`:** tryb zastępczy G3-B. Ustawia stan bez sprawdzania odpowiedzi MCP i oznacza wpis `marked_by_model: true`.

**`status`:** wypisuje JSON z liczbą wpisów w każdym stanie i 10 ostatnimi wpisami (bez treści materiału). Używane przez `bm-status`.

**Teksty.** Wartości z wpisu stanu podstawia skrypt; teksty są po angielsku, jak upstream.
- `<TEKST_CHECKPOINT>`: „Basic Memory checkpoint REQUIRED (context was just compacted). Before any other work, use the `basic-memory-nas:bm-checkpoint` skill in hook mode with: checkpoint_key={ck}, material file={material}, project={project or 'NOT SET – ask the user which Basic Memory project to use; never assume'}, folder={capture_folder}. The material file holds pre-compaction content that may be missing from your current context; read it in full. Then report in one line: `Checkpoint saved: <note reference>` or `Checkpoint NOT saved: <reason>`.”
- `<TEKST_RETRY>`: „Basic Memory has {n} unfinished checkpoint(s) from earlier sessions: {lista: ck, status, data, project, material}. Tell the user in one line, then complete each with `basic-memory-nas:bm-checkpoint` in hook mode, unless the user says to skip.”
- `<TEKST_ORIENT>`: „Basic Memory (NAS) is available. Before the first substantive task, use `basic-memory-nas:bm-orient` for project {primaryProject}. If no project is configured, ask the user which project to use (never mix `legal` and `main`). Keep it brief; if the tools are unavailable, say so in one sentence.”
- `<TEKST_STOP>`: „Basic Memory checkpoint {ck} is {status}. Finish it now with `basic-memory-nas:bm-checkpoint` in hook mode (write, then read back), or tell the user explicitly: `Checkpoint NOT saved: <reason>`.”

### 7.5. Format notatki checkpointu

Notatka zapisywana przez `bm-checkpoint` w trybie hooka:
- typ `session` (albo `coding_session` przy `sessionProfile: coding`, zgodnie z upstreamem), projekt `{project}`, folder `{capture_folder}`;
- tytuł: `Checkpoint {YYYY-MM-DD HH:MM} {krótki temat}`;
- metadata frontmatter: `checkpoint_key: {ck}`, `session_id`, `compaction_index`, `harness`, `status: active`;
- treść **musi** zawierać linię `checkpoint_key: {ck}`, bo z niej korzysta `post-tool`;
- sekcje: Problem, Approach, Decisions (lista numerowana z uzasadnieniem), Changes, Verification, Open questions / Blockers, Next action, Source material (krótko: segment transkryptu, `compaction_index`).

---

## 8. Nadpisania i patche skilli

Treść po angielsku, jak upstream.

### 8.1. `overrides/skills/bm-setup/SKILL.md`

1. `bm_project`. Brak narzędzi → plugin wymaga instalacji i autoryzacji w claude.ai/chatgpt.com. Koniec.
2. Wybór projektu z listy. **Bez domyślnego** (N8).
3. W Claude Code: zapis bloku `basicMemory` (`primaryProject`, `captureFolder`, opcjonalnie `sessionProfile`/`repository`) do `.claude/settings.json` projektu albo `~/.claude/settings.json`, według wyboru użytkownika. W czacie tylko podanie ustawień.
4. Schematy `session`, `decision`, `task`, `coding_session` przez narzędzia MCP, według logiki upstreamu.
5. Opcjonalnie `outputStyle: basic-memory`.

Usunięte: instalacje, `bm install`, `npx skills add`, wybór local/cloud, `basic-memory hook status`.

### 8.2. `overrides/skills/bm-status/SKILL.md`

Raport zawiera:
- projekt z ustawień;
- `bm_project`;
- 3 ostatnie checkpointy (`bm_search` po typie i folderze);
- liczbę aktywnych zadań;
- **stan kolejki checkpointów:** jeśli dostępna jest powłoka, `python3 <plugin_root>/hooks/bm_hook.py status`. Wpisy inne niż `saved` wyróżnij. Gdy powłoki nie ma (czat), wyjaśnij, że kolejka istnieje tylko lokalnie na hostach z hookami.

### 8.3. `overrides/skills/memory-doctor/SKILL.md`

Wariant według G4.

**G4-A:**
1. Sprawdź dostępność Admin Tools (`portal_codemode_search`/`portal_codemode_execute`). Brak → podaj polecenie do ręcznego uruchomienia i zakończ.
2. Znajdź kontener: `portainer_docker_proxy` GET `/containers/json` z projekcją.
3. Sprawdzenie tożsamości środowiska: exec listy projektów musi zgadzać się z `bm_project`. Rozbieżność → STOP.
4. Exec `basic-memory doctor --skip-self-test --json [--project X]`.
5. Analiza i raport **tylko do odczytu**. Nigdy nie wyświetlaj zmiennych środowiskowych kontenera.
6. Naprawy (np. `basic-memory reindex …`) wyłącznie po wyraźnej zgodzie użytkownika. Każde polecenie potwierdzane osobno.
7. Zakazane: usuwanie rekordów embeddingów, zmiana modelu embeddingów, `--self-test`, restart stacka.

**G4-B:** punkty 1–2 i 5–7 bez zmian, punkty 3–4 zastępuje instrukcja ręczna.

### 8.4. `patches/skills/bm-checkpoint.patch`

Dodaje sekcję „Hook mode”, gdy wywołanie zawiera `checkpoint_key`:
1. Przeczytaj w całości plik materiału (narzędzie Read albo powłoka). Brak pliku → kontynuuj z samego kontekstu i zaznacz to w notatce.
2. Projekt: z polecenia. Gdy jest `NOT SET`, zapytaj użytkownika. Nigdy nie przyjmuj domyślnego.
3. Deduplikacja: `bm_search` po metadanych `checkpoint_key = {ck}` w projekcie (skill `memory-metadata-search`).
   - Notatka istnieje → `bm_edit` (uzupełnienie).
   - Notatka nie istnieje → `bm_write` według 7.5.
4. Odczyt kontrolny: `bm_read` zapisanej notatki. Odpowiedź musi zawierać `checkpoint_key: {ck}`.
5. Raport jednej linii: `Checkpoint saved: <ref>` albo `Checkpoint NOT saved: <reason>`. Sukcesu nie wolno ogłaszać bez udanego odczytu kontrolnego.
6. Jeśli działa tryb zastępczy G3-B, wywołaj `bm_hook.py mark`.

Treść notatki łączy materiał (fakty sprzed kompakcji) i bieżący kontekst. Decyzje z materiału muszą trafić do sekcji Decisions bez pomijania.

### 8.5. `patches/skills/bm-orient.patch`

Brak `primaryProject` → zapytaj użytkownika o projekt. Usuń odwołania do lokalnego CLI (`basic-memory hook status`), jeśli występują.

### 8.6. `patches/skills/memory-okf.patch`

Przy operacjach wymagających CLI: „On self-hosted Basic Memory the CLI runs only inside the server container; use the remote execution path of `basic-memory-nas:memory-doctor` or ask the user to run the command.”

---

## 9. CI

### 9.1. `ci.yml`

Wyzwalacze: `push` i `pull_request`. Kroki:
1. Checkout repo oraz upstream na `build-info.json.upstream_sha`.
2. Python 3.12, Node 22, `npm i -g @anthropic-ai/claude-code`, `gitleaks`.
3. `python scripts/build.py --upstream ./upstream --out . --check`
4. `python scripts/check.py`

### 9.2. `sync-upstream.yml`

Wyzwalacze: `schedule: cron "23 3 * * *"` (raz dziennie) i `workflow_dispatch`. Kroki:
1. Checkout repo i upstream `main`.
2. `build.py`, potem `check.py`. Błąd → issue „upstream sync failed” z logiem (bez sekretów). Koniec.
3. Brak zmian → koniec.
4. PR z gałęzi `sync/upstream-<shortsha>`. W opisie:
   - zakres SHA;
   - lista zmienionych skilli z liczbą zmienionych linii;
   - zmiany hashy nadpisanych skilli jako ostrzeżenia;
   - zmiany w hookach i manifestach upstreamu (`plugins/claude-code/hooks/**`, `plugins/codex/hooks/**`) jako sygnał do ręcznej oceny, mimo że nie są kopiowane.
5. Etykieta `needs-review`. **Brak auto-merge** (N7).
6. Ochrona `main`: wymagane zielone `ci.yml` i ręczny merge.

---

## 10. Cloudflare Access (`bm.xlap.pl`)

Wykonawca tylko sprawdza (odczyt przez Admin Tools → `mcp_cloudflare_execute`) i raportuje. Zmiany wymagają zgody użytkownika. Wymagane:
1. Aplikacja Access z managed OAuth dla MCP i polityką Allow dla tożsamości użytkownika.
2. Dozwolone przekierowania OAuth, jeśli konfiguracja je ogranicza:
   - callback claude.ai (adres ustalony w G0-C);
   - `https://chatgpt.com/connector_platform_oauth_redirect`.
3. DCR włączone.
4. Polityka Service Auth może pozostać dla innych klientów. Plugin z niej nie korzysta.
5. Brak reguł `bypass`.

---

## 11. Fazy wdrożenia

### F0. Repo, audyt i sonda platform
1. Utwórz publiczne repo z `LICENSE`, `README.md`, `docs/PLAN.md` (ten dokument) i `docs/VERIFICATION.md`. Gałąź `impl/v1`. Ochrona `main` (wymagany CI, ręczny merge).
2. **Audyt istniejących źródeł**, tylko odczyt, wynik w VERIFICATION.md:
   - **MacBook, Claude Code:**
     - `claude plugin list`;
     - `/mcp`;
     - zawartość `~/.claude/skills` (nazwy);
     - wpisy `mcpServers` w `~/.claude.json` i `~/.claude/settings.json` odnoszące się do Basic Memory;
     - `syncClaudeAiPlugins`.
   - **MacBook, Codex:**
     - `~/.codex/config.toml`: sekcje `[mcp_servers.*]`, `[plugins.*]`, wpisy Basic Memory, w tym `mcp_servers.basic_memory` i `codex@basic-memory` (U18);
     - lista pluginów;
     - `~/.agents/plugins/marketplace.json`;
     - `~/.agents/skills` (nazwy).
   - **Holyclaude** (oba kontenery): to samo dla Claude Code i Codex, plus `~/.agents/` i konfiguracja `agents-sync`.
   - **claude.ai i ChatGPT:** lista konektorów, pluginów i wgranych skilli.
   - W audycie zapisuj nazwy i ścieżki, nigdy wartości sekretów.
3. Sonda G0: `probe/claude` i `probe/openai`, następnie G0-C (w tym G1) i G0-O.
4. Uzupełnij `config/build.json`: `openai_variant`, `openai_app_id`, `claude_tool_prefix` (z prefiksem docelowej nazwy pluginu, ustalonym z wzorca nazw z G1).

**Akceptacja:** audyt kompletny, G1-A, wynik G0-O zapisany (R, M albo X).

### F1. Hook
1. Pobierz jeden prawdziwy transkrypt Claude Code z kompakcją (MacBook, `~/.claude/projects/...`). Ustal znacznik granicy kompakcji. **Nie commituj** transkryptu. Na jego wzór utwórz syntetyczne fixture'y w `tests/fixtures/` (fikcyjna treść).
2. Zaimplementuj `bm_hook.py` (7.3, 7.4).
3. `tests/test_bm_hook.py`:
   - limit materiału i priorytety;
   - granica kompakcji;
   - uszkodzone linie;
   - przejścia stanów `pending → written → saved` i `failed`;
   - deduplikacja `ck`;
   - `stop` blokuje jeden raz i nie blokuje przy `stop_hook_active`;
   - retencja i `stale`;
   - uprawnienia `0600`/`0700`;
   - współbieżny zapis (dwa procesy);
   - brak `primaryProject` → `project: null` i tekst z „NOT SET”;
   - transkrypt 50 MB < 5 s (test oznaczony `slow`).

**Akceptacja:** `pytest` zielony.

### F2. Build
`build.py`, `check.py`, `test_build.py`, `test_negative.py`, `.gitleaks.toml`. Nadpisania tymczasowo jako kopie upstreamu.

**Akceptacja:** `pytest` zielony, w tym testy negatywne. `check.py` na gałęzi może jeszcze zgłaszać `forbidden_strings` w tymczasowym `bm-setup`. To jest stan pośredni gałęzi, **bez merge**.

### F3. Skille i G4
Wykonaj G4. Napisz nadpisania (8.1–8.3) i patche (8.4–8.6).

**Akceptacja:**
- `build.py --check` i `check.py` zielone w całości, 24 skille;
- `claude plugin validate --strict` OK;
- G4 zapisana.

**[MERGE]** `impl/v1` → `main`.

### F4. claude.ai
1. Usuń sondę `bm-probe` z claude.ai. Dodaj marketplace `elconcept/basic-memory-plugin`, zainstaluj `basic-memory-nas`, połącz MCP.
2. Test w czacie webowym:
   - `bm_project`;
   - `bm_write` i `bm_read` notatki `plugin-smoke-<data>` (projekt `main`, folder `tests`);
   - skille `basic-memory-nas:memory-notes` i `basic-memory-nas:bm-orient`.
3. Duplikaty (N3, N4): w Ustawieniach brak wgranych skilli Basic Memory; jeden konektor Basic Memory (z pluginu).

**Akceptacja:** punkty 2 i 3 spełnione.

### F5. Claude Code
Na MacBooku i w obu kontenerach holyclaude:
1. Wersja ≥ 2.1.273, logowanie kontem (`/status`). Klucz API → STOP dla hosta.
2. `syncClaudeAiPlugins` ≠ `false`.
3. **Czyszczenie z kopią (N9)** według audytu F0. Przenieś do kopii zapasowej:
   - katalogi `~/.claude/skills/{memory-*,bm-*}` i `~/.agents/skills/{memory-*,bm-*}`;
   - wpisy MCP Basic Memory spoza pluginu;
   - pluginy `basic-memory@basicmachines-co`.

   W `agents-sync` usuń linkowanie tych skilli. Każdy przeniesiony element wpisz do VERIFICATION.md.
4. Restart. `/plugin`: `basic-memory-nas` raz. `/mcp`: jeden serwer Basic Memory, *connected*. Nazwy narzędzi zgodne z `claude_tool_prefix`.
5. `basicMemory.primaryProject` przez `/basic-memory-nas:bm-setup`:
   - holyclaude-legal: `legal`;
   - główny holyclaude: `main`;
   - MacBook: według użytkownika.
6. Test potoku D5 (MacBook):
   1. Nowa sesja: blok orientacji.
   2. Praca. `/compact`.
   3. `bm_hook.py status`: wpis `pending` → po działaniu modelu `saved`.
   4. Notatka w NAS zawiera `checkpoint_key`.
7. Test N6:
   - tymczasowo ustaw w `.claude/settings.local.json` testowego katalogu `primaryProject` na nieistniejący projekt, potem `/compact`;
   - oczekiwane: `failed` w stanie, blokada `Stop` jeden raz, komunikat `Checkpoint NOT saved: …`, a w kolejnej sesji blok ponowienia;
   - przywróć ustawienie, ponów i oczekuj `saved`.

**Akceptacja:** punkty 4, 6 i 7 spełnione na MacBooku. Punkt 4 i 6 na co najmniej jednym kontenerze.

### F6. Cowork i G5
Test skilli i MCP jak w F4 pkt 2, potem G5.

**Akceptacja:** skille i MCP działają. G5 zapisana.

### F7. ChatGPT i G2
(Tylko przy G0-O-R lub G0-O-M.)
1. Usuń sondę.
2. Zainstaluj `basic-memory-nas` ścieżką z G0-O.
3. Test jak w F4 pkt 2 (w ChatGPT).
4. Duplikaty: jeden zestaw narzędzi Basic Memory. Plugin z rejestracji połączenia wyłączony lub ukryty według G0-O pkt 5.

**Akceptacja:** testy i brak duplikatów.

### F8. Codex i G3
1. **Czyszczenie z kopią (N9)** według audytu F0:
   - wyłącz i odinstaluj `codex@basic-memory`;
   - przenieś sekcję `[mcp_servers.basic_memory]` z `config.toml` do kopii zapasowej. Edytuj plik tylko po zrobieniu jego pełnej kopii;
   - usuń stare skille Basic Memory z `~/.agents/skills`.
2. Instalacja `basic-memory-nas` ścieżką z G0-O.
   - Marketplace osobisty `~/.agents/plugins/marketplace.json` (źródło git, `openai/`, `ref: main`);
   - na holyclaude przez źródłowy `~/.agents/` i `agents-sync`.
3. Zatwierdź (trust) hooki po przejrzeniu `hooks.json`.
4. G3, potem test potoku D5 jak w F5 pkt 6–7 (w trybie G3-A lub G3-B).
5. Sprawdź, że w Codex jest dokładnie jeden zestaw `bm_*`.

**Akceptacja:** jeden zestaw `bm_*`, MCP bez `codex mcp login`, potok D5 zakończony `saved`.

### F9. Aktualizacje i G6
1. `workflow_dispatch` dla `sync-upstream.yml`. Przy braku zmian brak PR.
2. G6: sztuczna zmiana w `overrides/skills/bm-status/SKILL.md` (komentarz), PR, merge, obserwacja na wszystkich powierzchniach.

**Akceptacja:** tabela G6.

### F10. Test ciągłości pamięci (kryterium odbioru)

Wykonaj na MacBooku w Claude Code, a następnie w Codex (jeśli F8 zaliczone). Projekt `main`, folder `tests/continuity`. **Nie używaj projektu `legal`.**
1. Nowa sesja. Przeprowadź analizę testową (temat neutralny, np. wybór formatu kopii zapasowej). Zapisz w rozmowie 6 decyzji, każdą z unikalnym znacznikiem `CT-<data>-D1` … `D6` i krótkim uzasadnieniem.
   - D1 i D2 podaj **na początku** sesji, potem wygeneruj długi materiał (np. poproś o szczegółowe porównania), żeby D1 i D2 znalazły się daleko od końca.
2. `/compact`, a gdy da się wywołać, także kompakcja automatyczna.
3. Sprawdź:
   - stan `saved`;
   - `bm_search` po `CT-<data>` zwraca notatkę checkpointu zawierającą **wszystkie 6** znaczników z uzasadnieniami.
4. Zamknij sesję. Nowy proces lub `/clear`. Zapytaj: „Jakie decyzje podjęliśmy w analizie CT-<data> i dlaczego?”. Model ma je odtworzyć z Basic Memory, nie z kontekstu.
5. Kryterium:
   - 6/6 decyzji odtworzonych z poprawnym uzasadnieniem;
   - każda poparta odwołaniem do notatki;
   - zero wpisów niezakończonych w `bm_hook.py status`.

   Wynik 5/6 lub mniej oznacza niezaliczony odbiór. Do VERIFICATION.md wpisz, której decyzji brakuje i na którym etapie zginęła (materiał, notatka, odtworzenie).
6. Usuń notatki `tests/continuity` i `plugin-smoke-*` po zapisaniu wyniku.

**Akceptacja całego wdrożenia:** F10 zaliczony na Claude Code. Na Codex zaliczony albo ograniczenie z G3 udokumentowane.

### Wycofanie
- **claude.ai:** odinstaluj plugin i usuń marketplace. Przywrócenie ręcznego konektora wymaga decyzji użytkownika (C7).
- **ChatGPT:** odinstaluj plugin. Połączenie z rejestracji może pozostać.
- **Hosty:** przywróć elementy z `~/.bm-migration-backup/<ts>/` według listy w VERIFICATION.md.
- **Repo:** `git revert` merge'a. Plugin dostaje wersję `N+1` z poprzednią zawartością.

---

## 12. Zakazy dla wykonawcy

1. Żadnych sekretów w repo, manifestach, plikach MCP, skillach, PR, issue ani w VERIFICATION.md, w tym wartości `Config.Env`.
2. Bez oficjalnych pluginów Basic Memory (Claude i Codex), bez `bm install`, bez `npx skills add` i bez lokalnego `basic-memory` na klientach.
3. Bez zmian w Cloudflare (trasy, bypass, polityki) bez zgody użytkownika.
4. Bez modyfikacji kontenera, stacka i bazy na NAS. Wyjątki: odczyty i exec z G4 oraz naprawy `memory-doctor` zatwierdzone przez użytkownika.
5. Bez usuwania notatek poza `plugin-smoke-*` i `tests/continuity` utworzonymi w tym wdrożeniu.
6. Bez ręcznej edycji `claude/` i `openai/`.
7. Bez merge'a do `main` poza punktami [MERGE] i PR zatwierdzonymi przez użytkownika.
8. Bez usuwania czegokolwiek z konfiguracji hostów bez kopii (N9).
9. Bez commitowania prawdziwych transkryptów i materiałów checkpointów.
10. Wynik bramki spoza opisanych wariantów: STOP i zgłoszenie.

---

## 13. Rozstrzygnięcia (zatwierdzone przez recenzenta)

| Kwestia | Decyzja |
|---|---|
| Fallback G1 na konektor konta | Brak automatycznego fallbacku. STOP i osobna decyzja. |
| Domyślny projekt | Brak. Jawny `primaryProject` albo pytanie. `legal` i `main` rozdzielone. |
| `memory-literary-analysis` | Wykluczony. 24 skille. |
| Sync upstreamu | Raz dziennie, zawsze PR, bez auto-merge |

---

## Źródła

- Upstream `basicmachines-co/basic-memory`:
  - `plugins/claude-code/README.md`, `plugins/claude-code/hooks/*`;
  - `plugins/codex/hooks/hooks.json`, `plugins/codex/.mcp.json`;
  - `scripts/build_skills_dist.py`, `scripts/validate_skills.py`;
  - `src/basic_memory/api/app.py`, `src/basic_memory/mcp/async_client.py`;
  - `src/basic_memory/cli/commands/hook.py` (`_transcript_turns`, `_checkpoint_note`, `CODEX_CHECKPOINT_PROMPT`);
  - `src/basic_memory/cli/commands/doctor.py`.
- Claude: support.claude.com/en/articles/13837440, support.claude.com/en/articles/11175166, code.claude.com/docs/en/plugins-reference, code.claude.com/docs/en/hooks
- OpenAI: developers.openai.com/plugins/build/plugins, developers.openai.com/plugins/deploy/submission, developers.openai.com/codex/mcp, learn.chatgpt.com/docs/plugins, help.openai.com/en/articles/12584461
- github.com/anthropics/claude-code/issues/65426