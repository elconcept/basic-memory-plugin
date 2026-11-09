# Plan v1.2 — Basic Memory NAS: pełne wykorzystanie upstreamu i ciągłość pamięci

**Status:** DRAFT — do niezależnej recenzji przez Claude; implementacja wyłącznie w granicach zadań i bramek poniżej.  
**Data:** 2026-11-09  
**Repo:** `elconcept/basic-memory-plugin`; gałąź robocza `impl/v1`  
**Kanoniczny punkt odniesienia:** [PLAN v1.1](PLAN.md) oraz [recenzja GPT](REVIEW_GPT_2026-11-09.md). Ten dokument uzupełnia i koryguje v1.1; nie nadpisuje oryginału.  
**Upstream:** `basicmachines-co/basic-memory`, `main`, bazowy commit `b7d4006bd581c80c2bf4e4ca9a95f745ccee83a5` (2026-11-08).  
**Środowisko:** Basic Memory self-hosted na Synology, `https://bm.xlap.pl/mcp` za Cloudflare Access; klienci: claude.ai, Claude Code, Cowork, ChatGPT, Codex, holyclaude.  
**Priorytet użytkownika:** maksymalna zgodność z aktywnym upstreamem; żadnego dużego forka, żadnego lokalnego Basic Memory na MacBooku, żadnych tymczasowych kopii dużych danych na MacBooku. Maintenance: **holyclaude + scheduled prompt**, **bez harmonogramu DSM**.

## A. Kluczowe rozstrzygnięcia względem v1.1

1. **Rozszerzyć cel z "przeżyć kompakcję" na system pamięci `recall → capture → consolidate`.** Checkpoint nadal chroni przed kompakcją, ale decyzje i istotne ustalenia muszą być utrwalane w trakcie pracy, nie tylko podczas kompakcji.
2. **Rozdzielić odpowiedzialność:** serwer NAS odpowiada za bazę, graf, indeksy, import, schematy i MCP; plugin za dystrybucję skilli, routing projektu, semantykę użycia MCP i hooki; holyclaude za aktywne, zaplanowane porządkowanie wiedzy; GitHub Actions za upstream-sync i CI.
3. **Nie budować własnych odpowiedników** `memory-reflect`, `memory-curate`, `memory-defrag`, `memory-lifecycle`, `memory-capture`, `bm-decide`, `bm-remember` czy `bm-orient`. Zachować upstream i najwyżej cienkie, jawnie uzasadnione poprawki zgodności transportu i nazw.
4. **Scheduler:** uruchamiać cztery skille maintenance przez już zainstalowany w HolyClaude **`cloudcli-cron` v0.2.0** (Scheduled Prompt) jako nowe lokalne procesy Claude Code. To nie jest DSM, sesyjny Claude Code `/loop` ani chmurowy `/schedule`. Audyt 2026-11-09: katalog pluginu obecny, manifest/package v0.2.0, liczba ledgerów `*.json` = 0. Brak jeszcze dowodu aktywnego schedule/MCP. Procedura i prompty: [HOLYCLAUDE_SCHEDULED_PROMPTS.md](HOLYCLAUDE_SCHEDULED_PROMPTS.md).
5. **Upstream GitHub worker:** codzienny GitHub Actions monitoruje `basicmachines-co/basic-memory/main`, aktualizuje pin i kontrolowany snapshot wejściowych skilli/manifestów, uruchamia walidację i tworzy/aktualizuje PR `sync/upstream`. Po dostępności budowniczego artefaktów dodatkowo regeneruje `claude/` i `openai/`. **Nie scala PR automatycznie** (utrzymany N7 z v1.1).
6. **Bezpieczeństwo:** jawne `primaryProject`, brak automatycznego routingu `null` do `main` lub `legal`; jawne potwierdzenie MCP przed `saved`; brak sekretów w publicznym repo, logach i narzędziach; kopie konfiguracji przed zmianą; żadnych usunięć notatek bez zgody.
7. **Bez ingerencji w produkcyjne dane na starcie:** testy w projekcie testowym lub ściśle wyodrębnionym folderze. `legal` nigdy nie jest testowym poligonem.
8. **Commit po każdym zadaniu:** atomiczny zakres, test, dokumentacja dowodu. Branch `impl/v1`; merge do `main` dopiero po CI i przeglądzie. Harmonogram GitHub Actions **nie działa na gałęzi roboczej** (scheduled workflows działają na domyślnej gałęzi); "skonfigurowany" i "aktywny" to dwa różne stany.

## B. Matryca funkcjonalności — docelowa kwalifikacja

| Zakres | Upstream | Warstwa docelowa | Kryterium |
|---|---|---|---|
| Pisanie/czytanie/edycja/przenoszenie/usuwanie | `bm_write`, `bm_read`, `bm_edit`, `bm_move`, `bm_delete` | NAS MCP | Smoke CRUD, wersjonowanie i blokada zapisów |
| Wyszukiwanie i graf | `bm_search`, `bm_find`, `bm_list`, `bm_context` | NAS + skille recall | Trafność tekstowa/wektorowa, izolacja projektów |
| Projekty | `bm_project`, `bm_project_delete` (opt-in) | NAS MCP + plugin routing | Jawna identyfikacja, żadnych `null` fallback |
| Schematy | `bm_schema`, `memory-schema` | NAS + onboarding | Infer/validate/diff, typowane decyzje i zadania |
| Notatki i relacje | `memory-notes`, `memory-metadata-search` | skille obu klientów | Ustrukturyzowane metadane, linki |
| Odtworzenie pracy | `memory-continue`, `bm-orient`, `bm-checkpoint` | klient + MCP | Niezależny nowy proces, powiązanie checkpointów |
| Bieżący zapis | `memory-capture`, `bm-decide`, `bm-remember`, `bm-writing` | klient + MCP | Decyzje zachowane także bez kompakcji |
| Zadania i cykl życia | `memory-tasks`, `memory-lifecycle` | skille, holyclaude | Zadania aktywne i archiwum bez kasowania |
| Refleksja i higiena | `memory-reflect`, `memory-curate`, `memory-defrag` | **holyclaude scheduled prompts** | Raport, propozycje zmian, kontrolowany zapis |
| Import | `memory-ingest`, CLI import / opcjonalne ekstraktory | NAS/holyclaude | Pochodzenie, bez naruszania oryginałów |
| Diagnostyka i eksport | `memory-doctor`, `memory-okf`, CLI inspect/doctor | NAS, procedury read-only | Raport; naprawa tylko po akceptacji |
| Wyszukiwanie po polsku | full-text, vector, hybrid; opcjonalny reranker | NAS | Benchmark polskich zapytań przed tuningiem |
| Cloud-only | `memory-agents`, `memory-quest`, interaktywny render Comark | poza self-hosted | Nie przedstawiać jako lokalnych funkcji |
| Upstream sync | GitHub Actions + PR | GitHub | Dzienny schedule, CI, diff SHA, bez auto-merge |

Wszystkie powyższe nazwy/narzędzia należy zweryfikować introspekcją rzeczywistego MCP przez `bm_man`; obecność skilla nie implikuje dostępności narzędzia/CLI w wdrożonym kontenerze. Nie należy sztucznie narzucać tej samej liczby skilli Claude i Codex, jeśli upstream różnicuje ich zbiory.

## C. Holyclaude scheduled prompts (zamiast DSM)

**Osobny zestaw czterech scheduled prompts, tylko na holyclaude:**

| Prompt | Sugerowana częstotliwość (do zatwierdzenia) | Tryb |
|---|---|---|
| `memory-reflect` | 1× dziennie, poza godzinami pracy | Odczyt najnowszych notatek, synteza trwałych ustaleń; propozycje konfliktów |
| `memory-curate` | 1× tydzień | Raport osieroconych notatek, relacji, duplikatów i propozycji korekt |
| `memory-defrag` | co tydzień (proposal-only; alternatywnie co miesiąc) | **Najpierw plan/raport**, bez kasowania i bez niezatwierdzonych scaleń. Plugin v0.2.0 nie ma cyklu co 2 tygodnie |
| `memory-lifecycle` | 1× tydzień | Zidentyfikowanie zadań do zamknięcia/archiwizacji; domyślnie propozycje, brak delete |

**Każdy prompt**: jawny projekt; nigdy `legal` + `main` w jednym wykonaniu; read-only audit przed mutacją; krótki raport wraz z odnośnikami do notatek; provenance i decyzje użytkownika zachowane; brak samodzielnych usunięć, retroaktywnego przeredagowywania dowodów, wymyślania brakujących danych. Prompt obejmuje tylko skille i narzędzia potwierdzone na danym kliencie. Odmowa lub brak działania MCP = jawny raport, nie cichy sukces.

**Weryfikacja schedulera:** `cloudcli-cron` v0.2.0 jest zainstalowany i ma pusty katalog ledgerów. Pozostają: weryfikacja aktywacji w CloudCLI UI, strefy czasowej, poświadczeń CLI, dostępu do MCP ze świeżego procesu i historii wykonania. Nie zastępować lokalnego schedulera chmurowym `/schedule` ani sesyjnym `/loop`. Uruchomić `Run Now` w osobnym projekcie testowym, według [procedury operacyjnej](HOLYCLAUDE_SCHEDULED_PROMPTS.md).

## D. Bramki technologiczne i bezpieczeństwa

- **G0-Platform**: konta Claude/ChatGPT/Codex, plugin API, autoryzacja OAuth i dziedziczenie między aplikacjami potwierdzone osobnymi testami read/write/readback; negatywny wynik nie blokuje niezależnego artefaktu.
- **G0-NAS**: przez Portainer wyłącznie projekcja po stronie serwera; nigdy pełne `Config.Env` do modelu; sprawdzić identyczność bazy serwera i CLI oraz działanie `bm_man`, `bm_schema`, `bm_context`, `bm_search`.
- **G0-Holyclaude**: rzeczywisty scheduler i historia wykonania, izolacja projektów, prompt z MCP i skutecznym raportem.
- **G0-GitHub**: permissions Actions, harmonogram na default branch, obsługa PR, branch protection, udany manual test. Żadnego auto-merge.
- **G1-Continuity**: przejście `pending → written → saved` tylko po odczycie tej samej notatki/ref i projektu. `unassigned`, `capture_failed`, `PostToolUseFailure`, wielosesyjność i błędy rozłączne.
- **G2-Data**: 6/6 wczesnych decyzji odtworzonych z nowej sesji po kompakcji **i osobno bez kompakcji**. Dwie kompakcje, brak transkryptu, błąd dysku i utrata OAuth testowane.
- **G3-Upstream**: stały snapshot porównywalny z pinned SHA, raport zmian, niezmienione pliki upstreamowe, licencje, PR do przejrzenia. Rozbieżność API/formatu → FAIL, nie automatyczna improwizacja.

**Uwaga licencyjna:** główny projekt upstream deklaruje AGPL-3.0-or-later, katalog skilli i plugin Claude opisują MIT. Przed publikacją vendoringu sprawdzić zakres licencji plików i zachować notices. Nie przyjmować, że deklaracja MIT obejmuje wszystkie źródła upstreamu.

## E. Zadania atomowe (jeden commit na ukończone zadanie)

| Task | Zmiana | Test / dowód | Zależność |
|---|---|---|---|
| **T00** | Ten dokument `docs/PLAN_v1.2_DRAFT.md` do recenzji Claude | Link do commitu i nietknięty v1.1 | brak |
| **T01** | `docs/FEATURE_MATRIX.md` ze źródłami, zakresem i statusem każdego komponentu | Porównanie z upstream SHA i spis luk | T00 |
| **T02** | Dzienny GitHub upstream worker, skrypt wykrywania i snapshot/PR, jednostkowe testy | Manual-run lub kontrola składni; odczyt rzeczywistego stanu workflow | T00 |
| **T03** | CI: testy Pythona, walidacja snapshotu, skan sekretów, ochrona PR | Green CI; brak sekretów w logach | T02 |
| **T04** | Minimalny generator obu artefaktów zgodny z upstream + profile `claude`/`openai` | Deterministyczny build, brak duplikatów, bez kodu upstream poza snapshot | G0-Platform, T01 |
| **T05** | Hooki kolejki checkpointów i przechwytywania, odporne na błędy | Testy stanów, izolacji, współbieżności | T04 |
| **T06** | Setup, native `bm-*`, skille `memory-*`, output style i decyzje live | Testy recall/capture/schema/provenance | T04, T05 |
| **T07** | Testy platform Claude/ChatGPT/Codex/Cowork; migracja z kopią | G0 i G1, brak duplikatów | T06 |
| **T08** | Aktywacja `cloudcli-cron` v0.2.0 (już zainstalowany), cztery prompty, `Run Now` i pierwszy scheduled run | G0-Holyclaude + raport; [prompty](HOLYCLAUDE_SCHEDULED_PROMPTS.md) | T06 |
| **T09** | Diagnostyka i funkcje NAS: schematy, search benchmark PL, kontrola rewizji, import | G0-NAS + benchmark, bez niezamówionych migracji | T01 |
| **T10** | Kompletny E2E continuity, rollback, review i merge | G2, G3, raport końcowy | T02–T09 |

**Atomiczny workflow:** przed zadaniem sprawdzić status repo; wyłącznie pliki zadania; walidacja; commit `Txx: ...`; zapisać SHA, stan i ograniczenia w `docs/IMPLEMENTATION_LOG.md` w ramach tego samego commitu lub następnego dedykowanego tasku. Żadnego łatania w tle i łączenia kilku zadań w jednym commicie. Kosztowne testy integracyjne po osobnych checkpointach.

## F. Szczegółowa specyfikacja T02 — upstream worker

- GitHub Actions `schedule: '23 3 * * *'` (UTC) + `workflow_dispatch`; domyślna gałąź po zatwierdzonym merge.
- Minimalne uprawnienia: `contents: write`, `pull-requests: write` w samym workflow; bez sekretów osobistych; tylko `GITHUB_TOKEN`.
- Źródło upstream pobrane na runnerze GitHub Actions, nie na MacBooku. Bazowy commit jawnie przechowywany w `config/upstream.lock.json`.
- Aktualizacja snapshotu upstream zachowuje treść skilli/manifestów oraz commit SHA; żadnych zmian w kodzie samego upstreamu; ręczne nadpisania/patchowanie w osobnym katalogu.
- W PR: stare/nowe SHA, lista zmienionych plików, ostrzeżenia dotyczące API/manifests/hooków/licencji, status testów.
- Jeden branch `sync/upstream` oraz jeden otwarty PR; brak mnożenia PR codziennie. Każdy następny run uaktualnia branch tylko przy nowym SHA. Równoległe wykonania serializuje `concurrency`.
- Jeśli `build.py` już istnieje: zregeneruj pluginowe artefakty i sprawdź `--check`. Jeśli generator jeszcze nie został zaimplementowany: PR jest **źródłową aktualizacją staging** i ma status `not-release-ready`; nie twierdzić, że klient pluginu już zaktualizowano.
- Każda niespodziewana zmiana, konflikt, brak licencji, awaria walidacji lub brak dostępu do GitHub → fail i widoczny raport; nie merge.
- Bezpieczne akcje: nie uruchamiać kodu niezweryfikowanego PR w kontekście `pull_request_target`; nie ujawniać tokenów.
- Przygotowanie działającego workflow na `impl/v1` **nie włącza automatycznego cron**. Przed stwierdzeniem "worker aktywny" należy zweryfikować obecność workflow na `main`, status Actions, reguły repo i udany run.

## G. Weryfikacja przez Claude — wyjście recenzji

Claude powinien zwrócić `APPROVE` lub `REQUEST_CHANGES` dla każdego punktu, podając dokładny plik / sekcję / dowód:

1. Czy projekt pozostaje blisko szybko rozwijającego się upstreamu, bez przepisywania istniejących skilli lub serwera?
2. Czy `memory-reflect`, `memory-curate`, `memory-defrag`, `memory-lifecycle` mogą działać z **holyclaude scheduled prompts**, jakie są ograniczenia i wymagania dla rzeczywistego środowiska?
3. Czy worker w T02 ma poprawne `permissions`, `concurrency`, reakcję na błąd i potrafi naprawdę aktualizować artefakty, a nie jedynie pin SHA?
4. Czy `Claude Code`, `claude.ai`, `Codex` i `ChatGPT` dziedziczą połączenia/OAuth w opisany sposób? Wyniki niepotwierdzone oznaczyć jako bramki STOP.
5. Czy istnieje droga utraty/nieprawidłowego routingu notatki lub fałszywego `saved`? Przedstawić test negatywny.
6. Czy reżim licencyjny kopiowanych skilli/manifestów oraz zasada zamkniętego kodu użytkownika vs publiczny plugin są bezpieczne?
7. Czy proponowane funkcje serwera są faktycznie dostępne w self-hosted Basic Memory 1.0 na NAS (bez funkcji Cloud-only)?
8. Które części planu są w istocie zaimplementowane upstream i powinny zostać usunięte z zakresu własnego kodu?

**Warunek recenzji:** źródłem prawdy jest zweryfikowany kod, dokumentacja, wynik testu, nie intuicja modelu. Wszelkie propozycje zmian w planie należy dostarczyć jako konkretne diffy. Bez samodzielnego merge do `main`.

## Źródła

- https://github.com/basicmachines-co/basic-memory/tree/main/skills
- https://github.com/basicmachines-co/basic-memory/tree/main/plugins/claude-code
- https://github.com/basicmachines-co/basic-memory/tree/main/plugins/codex
- https://github.com/basicmachines-co/basic-memory/blob/main/plugins/claude-code/DESIGN.md
- https://github.com/basicmachines-co/basic-memory/blob/main/README.md
- https://github.com/elconcept/basic-memory-plugin/blob/main/docs/PLAN.md
- https://github.com/elconcept/basic-memory-plugin/blob/main/docs/REVIEW_GPT_2026-11-09.md
