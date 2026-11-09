# Basic Memory — macierz funkcji upstream vs. plan wdrożenia

**Task:** T01  
**Audyt kodu:** `basicmachines-co/basic-memory@b7d4006bd581c80c2bf4e4ca9a95f745ccee83a5`.  
**Metoda:** enumeracja ścieżek `SKILL.md` z drzewa GitHub danego SHA oraz weryfikacja `README.md`, `skills/README.md`, `plugins/claude-code/README.md`, `plugins/codex/README.md`, `plugins/claude-code/DESIGN.md`.  
**Granice:** to audyt *kodu upstream*, NIE potwierdzenie wersji i konfiguracji uruchomionego NAS ani dostępności funkcji w danym planie Claude/ChatGPT. `verified_on_nas = pending` dla wszystkich funkcji serwerowych.

## 1. Skille na wskazanym SHA: 20 globalnych, 8 Claude i 8 Codex

### Globalne `skills/memory-*/SKILL.md`

| Skill | Funkcja | Realizacja docelowa | W v1.1 |
|---|---|---|---|
| `memory-agents` | Zarządzanie agentami Basic Memory Cloud | **Wykluczyć**: Cloud-only | Wykluczony |
| `memory-capture` | Spójna notatka stanu wątku, aktualizacje po `thread_id` | **Włączyć** w bieżącym przepływie, także bez kompakcji | Skopiowany, bez triggerów |
| `memory-ci-capture` | Wewnętrzne skille CI | **Wykluczyć**: `metadata.internal` | Wykluczony |
| `memory-comark` | Wizualne dyrektywy Comark | Zachować tekst na self-hosted, renderer Cloud-only | Skopiowany |
| `memory-continue` | Wznowienie pracy z wiedzy | Aktywować na żądanie i wznowienie sesji | Skopiowany |
| `memory-curate` | Graf, relacje, duplikaty | **Holyclaude scheduled prompt** 1×/tydzień, raport przed zmianami | Skopiowany |
| `memory-defrag` | Refaktoryzacja nadmiernych/zdublowanych notatek | **Holyclaude scheduled prompt** raz w miesiącu, tylko propozycje (PLAN v1.2 F11) | Skopiowany |
| `memory-doctor` | Diagnostyka indeksów i zapisów | NAS read-only, naprawa po akceptacji | Nadpisany |
| `memory-ingest` | Strukturyzacja wejścia | Opcjonalne importy, provenance, bez zmian oryginału | Skopiowany |
| `memory-lifecycle` | Statusy, foldery, archiwum | **Holyclaude scheduled prompt** tygodniowy, bez automatycznych delete | Skopiowany |
| `memory-literary-analysis` | Analiza pełnej książki | **Wykluczyć**: wymaga lokalnego CLI / poza zakresem | Wykluczony |
| `memory-metadata-search` | Filtrowanie frontmatter | Zautomatyzować filtrowanie typu/statusu/projektu | Skopiowany |
| `memory-notes` | Struktura obserwacji i relacji | Kanoniczny format i provenance | Skopiowany |
| `memory-okf` | Kontrola zgodności i eksport OKF | Czytać przez MCP; CLI tylko na NAS | Skopiowany / patch |
| `memory-onboarding` | Schematy, router, indeksy, startup | Uruchamiać jawnie podczas konfiguracji nowego projektu | Skopiowany |
| `memory-quest` | Misje Basic Memory Cloud | **Wykluczyć**: Cloud-only | Wykluczony |
| `memory-reflect` | Okresowa refleksja nad trwałymi ustaleniami | **Holyclaude scheduled prompt** dzienny | Skopiowany |
| `memory-research` | Zewnętrzny research + notatki | Zachować z wymogiem prywatności zapytań | Skopiowany |
| `memory-schema` | `infer`, `validate`, `diff` | Seed + kontrola driftu | Skopiowany |
| `memory-tasks` | Aktywne zadania, status, kontynuacja | Typowane zadania, przypisywanie projektów | Skopiowany |

### Natywne `bm-*` — oddzielne źródła dla Claude Code i Codex

`bm-checkpoint`, `bm-decide`, `bm-orient`, `bm-remember`, `bm-setup`, `bm-share`, `bm-status`, `bm-writing`.

**Zasada:** pobierać każdą z tych ośmiu nazw z osobnych drzew `plugins/claude-code/skills/` oraz `plugins/codex/skills/`. Nie utożsamiać implementacji Claude i Codex. `bm-writing` i `bm-decide` tworzą warstwę aktywnego utrwalania decyzji; `bm-checkpoint` pozostaje zabezpieczeniem awaryjnym.

### Liczba skilli

- Upstream: **20** `memory-*`, **8** `bm-*` dla Claude, **8** `bm-*` dla Codex.
- Plan v1.1 wyklucza cztery nazwy globalne i kopiuje 16 + 8 = **24** dla każdego artefaktu.
- Liczba `24` jest poprawna dla wskazanego SHA i tego zbioru wykluczeń, ale powinna być *pochodną inwentaryzacji* w kolejnych upstream-sync PR; nagły nowy skill ma uruchamiać review, nie ciche pominięcie.

## 2. Warstwa MCP/CLI — funkcje serwera, nie pluginu

| API / funkcja | Gdzie działa | Status w planie v1.1 | Test wymagany na NAS |
|---|---|---|---|
| `bm_write`, `bm_read`, `bm_edit` | Serwer MCP | Smoke + checkpoint | Jawny projekt, note ID, readback |
| `bm_move`, `bm_delete` | Serwer MCP | Brak osobnego planu testów | Test na syntetycznej notatce, zatwierdzenie delete |
| `bm_search`, `bm_list`, `bm_find` | Serwer MCP | Pośrednio w skillach | Text + metadata + date / provenance |
| `bm_context` | Serwer MCP | Pośrednio `bm-orient` | Relacje w grafie, JSON |
| `bm_project`, `bm_project_delete` | Serwer MCP; delete za opt-in | Listy projektów i routing | Zero automatycznych delete; `project=null` fail closed |
| `bm_schema` | Serwer MCP | Seed `session`, `decision`, `task` | Infer, validate, diff |
| `bm_man` | Serwer MCP | Pominięte | Odczyt **bieżącego** kontraktu metod |
| `basic-memory doctor` | CLI w kontenerze NAS | `memory-doctor` | Read-only i zgodność bazy CLI/MCP |
| `bm inspect`, import/eksport | CLI na NAS | Częściowo/pominięte | Dokumentacja, test kontrolowany |
| Search vector/hybrid/reranking | Serwer, ustawienia i optional models | Brak benchmarku | Polski zbiór 20–50 zapytań, latency i precision |
| Odczyty fragmentów, rewizje, `locked` | Zależne od wersji MCP | Nieopisane | Introspekcja `bm_man` i testy, bez zakładania |
| Import PDF/DOCX/PPTX/CSV | CLI/worker i opcjonalne deps na NAS | Pominięte | Test małego dokumentu testowego |
| Cloud-only `search`/`fetch` adapter | Basic Memory Cloud | Nie mylić z self-hosted | Nie wymagać lokalnie |
| Basic Memory Cloud Agents | Usługa Cloud | Wykluczone | Nie implementować lokalnie |

## 3. Luki funkcjonalne v1.1

| Luka | Skutek | Rozwiązanie |
|---|---|---|
| Orientacja nie wykorzystuje dość precyzyjnego metadata search | Zbyt słaby recall lub niepotrzebne wyniki | `bm-orient` + type/status + aktualny projekt |
| Zależność od PreCompact | Znikające decyzje po sesji bez kompakcji | `bm-decide`, `bm-remember`, `memory-capture` w trakcie pracy |
| Brak procedur refleksji/higieny | Narastanie duplikatów i nieaktualnych zadań | Cztery scheduled prompts na holyclaude |
| Jeden wspólny `bm-*` katalog dla klientów | Utrata funkcji natywnych Codex | Dwa oddzielne zestawy upstream |
| Brak testów importu/chronologii/wersjonowania | Wykorzystanie tylko prostych notatek | Feature-gated testy NAS i ograniczone importy |
| Skromny test F10 | Nie wykrywa braków bez kompakcji | 6/6 także bez kompakcji i przy dwóch kompakcjach |
| Stałe kopie skilli bez różnic upstream | Nieaktualne skille i funkcje | GitHub sync PR z raportem SHA/zmian |
| Niejasny reżim licencji | Ryzyko niepoprawnego vendoringu | Audyt MIT/AGPL per katalog przed publiczną publikacją źródeł |

## 4. Warunki praktycznej dostępności

Oznaczenia stosowane w dalszej pracy:
- **SOURCE-VERIFIED** = istnieje w upstream@SHA.
- **NAS-VERIFIED** = potwierdzone w działającym MCP/CLI na Synology.
- **CLIENT-VERIFIED** = wywołanie MCP/skilla na docelowym Claude/ChatGPT/Codex.
- **SCHEDULED-VERIFIED** = prompt holyclaude ma zapisany termin oraz co najmniej jeden udany log wykonania.
- **GH-ACTIVE** = workflow na `main` + uruchomienie i wynik + prawa do tworzenia PR.

Obecnie ta macierz stwierdza tylko SOURCE-VERIFIED. Pozostałe statusy mają oddzielne bramki w [PLAN.md v1.2](PLAN.md).

## 5. Źródła do recenzji Claude

- https://github.com/basicmachines-co/basic-memory/tree/b7d4006bd581c80c2bf4e4ca9a95f745ccee83a5/skills
- https://github.com/basicmachines-co/basic-memory/tree/b7d4006bd581c80c2bf4e4ca9a95f745ccee83a5/plugins/claude-code
- https://github.com/basicmachines-co/basic-memory/tree/b7d4006bd581c80c2bf4e4ca9a95f745ccee83a5/plugins/codex
- https://github.com/basicmachines-co/basic-memory/blob/b7d4006bd581c80c2bf4e4ca9a95f745ccee83a5/README.md
