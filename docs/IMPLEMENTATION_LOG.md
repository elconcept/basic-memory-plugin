# Basic Memory NAS — stan wdrożenia i trwałe checkpointy

**Ostatnia aktualizacja:** 2026-11-09. **Branch implementacji:** `impl/v1`.  
**Plan obowiązujący:** [PLAN.md v1.2](PLAN.md) (draft v1.2 wchłonięty; odpowiedź Claude: [REVIEW_CLAUDE_2026-11-09.md](REVIEW_CLAUDE_2026-11-09.md))  
**PR do recenzji Claude:** https://github.com/elconcept/basic-memory-plugin/pull/4 (draft, bez merge)  
**Upstream worker:** https://github.com/elconcept/basic-memory-plugin/actions/workflows/sync-upstream.yml  
**Pierwszy PR upstream snapshot:** https://github.com/elconcept/basic-memory-plugin/pull/3 (draft, bez merge)

## Zakres wykonanych zmian (osobne commity)

| Commit | Zakres | Stan |
|---|---|---|
| `d7e85577` | Wersja planu v1.2 do recenzji | Zapisano |
| `3b232b96` | Macierz 20 `memory-*` i 8 `bm-*` na klienta | Zapisano |
| `22512288` | `scripts/sync_upstream.py`, testy i worker GitHub | Zapisano |
| `3e9b2080` | `ci.yml` (unittest, compile, gitleaks) | Zapisano |
| `c8f084d9` | Test na realnym upstream źródłowym `b7d4006` | CI PASS |
| `f4f74d62` | Synchronizacja poprawek workflow z `main` | Zapisano |
| `f33d11ea` | Wzorce czterech lokalnych scheduled prompts | Zapisano |
| `d40ee1ba` | Normalizacja dokumentów i aktualizacja architektury `cloudcli-cron` | Zapisano |
| `ffcd6a00` | Scalono zweryfikowaną infrastrukturę z `main` do branch implementacji | Zapisano |
| `aadabf8f` | Read-only preflight CLI Basic Memory na NAS | PARTIAL |
| `0edb83fb` | Ograniczenie publicznego raportu do nazw mountów kontenera | Zapisano |

**Uwaga o identyfikatorach:** etykiety `T05` i `T06` w wiadomościach *pomocniczych* commitów nie oznaczają ukończenia faz `T05 hooki` i `T06 skills` z tabeli planu v1.2. Dla jednoznaczności rozliczaj zadania według **zakresu plików i kryteriów odbioru**, nie wyłącznie numeru w commit message.

## Workflows GitHub — rzeczywiście sprawdzone

1. Infrastruktura wyodrębniona do PR #1, po zielonym CI scalona do `main` (`d1e445ad`).
2. Pierwszy manual run wykrył błąd `git add` nieistniejących katalogów `claude/`, `openai/` i `build-info.json`; naprawiono przez PR #2, po zielonym CI merge do `main` (`ef591399`).
3. Drugi manual `workflow_dispatch`: **SUCCESS**: https://github.com/elconcept/basic-memory-plugin/actions/runs/42636301294
4. Worker otworzył jedyny, **draft** PR #3 `sync/upstream` z kontrolowanym snapshotem źródeł. Nie scalono go, klient pluginu **nie** został jeszcze zaktualizowany.
5. `schedule`: codziennie `03:23 UTC`; workflow widoczny jako aktywny na `main`. Test rzeczywistego automatycznego wykonania o tej godzinie nastąpi dopiero po upływie pierwszego terminu.
6. Actions: `default_workflow_permissions=read`, opcja tworzenia PR przez workflow **enabled**, workflow sync ma minimalne jawne uprawnienia `contents: write` i `pull-requests: write`. CI używa `contents: read`.
7. `main` ma branch protection: PR wymagany, zielony `validate` wymagany w trybie strict, wymuszone także dla administratora, force-push/deletions wyłączone. **Brak auto-merge.**

## Holyclaude — stan rzeczywisty

- Kontener `/Holyclaude` działa.

## NAS Basic Memory — stan rzeczywisty

- Kontener `/basic-memory-server` działa, obraz `ghcr.io/basicmachines-co/basic-memory:latest`, proces pod `appuser`.
- CLI działa jako `/app/.venv/bin/basic-memory`, wersja **1.0.0**. W interaktywnym `docker exec` komenda `basic-memory` bez ścieżki nie znajduje się w `PATH`.
- `project list --json` przez CLI pokazuje tylko `main`. Porównanie z MCP i tożsamość danych pozostają **PENDING**. Nie wolno zakładać utraty innych projektów.
- Nie modyfikowano ani nie restartowano kontenera i bazy.

## Recenzja Claude i plan v1.2 (2026-11-09)

- R01–R13 przyjęte (cztery z modyfikacją), pytania 1–8 z draftu rozstrzygnięte: [REVIEW_CLAUDE_2026-11-09.md](REVIEW_CLAUDE_2026-11-09.md).
- `docs/PLAN.md` podniesiony do v1.2; `PLAN_v1.2_DRAFT.md` wchłonięty i usunięty (historia git). Obowiązuje jedna numeracja F/G, mapowanie T→F w PLAN §11.0.
- Blokery K1–K3 z tej recenzji **wycofane** w korekcie 1.2.1 (niżej).

## Korekta użytkownika, plan 1.2.1 (2026-11-09)

- **Licencja:** repo i plugin na AGPL-3.0-or-later. Dodany `LICENSE` w korzeniu i w `claude/`, `openai/`; `plugin.json` obu celów ma `license: AGPL-3.0-or-later`. Wcześniejsze MIT nie było uzgodnione z użytkownikiem.
- **Projekty:** wdrożenie vanilla, jeden projekt `main`. `legal`/`model-memory` to projekty dawnej, nieudanej instalacji, bez związku z tym wdrożeniem. Usunięte z planu, skilli i testów (`assign`/`allowedProjects` wycofane z planu).
- **Upstream:** worker commituje bezpośrednio na `main` po zielonych testach; ochrona gałęzi `main` zdjęta; PR #3 zamknięty. Blokady PR (draft, `needs-review`, wymagany `validate`, wymuszanie dla admina) nie były uzgodnione z użytkownikiem.
- **Do wykonawcy (F1b):** usunąć z `src/hooks/adapter.py` i `state_store.py` obsługę `assign`/`allowedProjects` i komunikat o braku `primaryProject`; projekt = `primaryProject` albo domyślny projekt serwera, a wpis z `project: null` przyjmuje projekt z pierwszego udanego zapisu (PLAN 1.2.1 N8, 7.4).

## Nieukończone etapy (dla następnego modelu)

1. **Claude review** PR #4: rygorystyczny audyt upstreama, schedulera i licencji; dopiero potem zmiana DRAFT → APPROVED.
2. **G0 Platform**: Claude/ChatGPT/Codex OAuth i plugin-distribution; osobny dowód dla narzędzi write/readback i dziedziczenia autoryzacji.
3. **T04 artefakty**: generator `claude/` oraz `openai/`, budowanie profilami, licencja i skille natywne klienta; obecny sync jest tylko snapshotem.
4. **T05 checkpoint state machine** oraz sesja bez kompakcji; testy negatywne przed migracją.
5. **T06 skille/setup**.
6. **T09** identyczność CLI/MCP, `bm_man`, schema, doktor i import; żadnych napraw bez wcześniejszej zgody.
7. **T10** end-to-end 6/6 z dwóch niezależnych sesji; dopiero wtedy propozycja merge do main.


## Kontynuacja wykonawcza — 2026-11-09, po recenzji Claude

Ten fragment koryguje historyczny stan powyżej; poprzednich wyników i błędów nie usunięto z dziennika.

| Commit | Zrealizowany zakres | Potwierdzenie |
|---|---|---|
| `a32b2780` | T04a: generator kandydatów `claude` i `openai`, osobne natywne skille, brak hooków i sekretów, testy | CI 42650263596 — PASS |
| `8f086a0a`, `465ddca0` | T04b: zamiany zakotwiczone w upstream, poprawiony test ścieżki overrides | CI 42651375371 — PASS |
| `303fb45a` | T04c: adaptacje `bm-setup`, `bm-status`, `memory-doctor` dla NAS (projekt bez lokalnej instalacji) | testy po poprawce — PASS |
| `d6b4ec18` | T04d: obie paczki generowane i porównywane na rzeczywistym `b7d4006` w CI | CI 42651451415 — PASS |
| `4a2125ee`, `49d40feb` | T04e/f: katalogi marketplace i ręczny GH Actions build+draft PR | runner 42651891422 — PASS |
| `dcfc6114` | T04f: PR #5 80 wygenerowanych plików, przetestowany i scalony **wyłącznie do `impl/v1`** | CI 42652071779 — PASS |
| `60703dc3` | F2: każdy patch przypięty do konkretnego Git blob SHA źródłowego skilla | CI 42653302434 — PASS |
| `c91f4644` | F9: wersja kandydatów zwiększana raz na nowe SHA upstream | CI 42653708782 — PASS |
| `c65dc03a` | F9: przygotowanie generowania i testów obu pakietów w PR workera na `impl/v1` | CI 42654068015 — PASS; **nieaktywne na `main`** |
| `3fdcfa34` | G4: odczytowe porównanie CLI, aktywnego MCP i nazw projektów konfiguracji | [NAS_MCP_PROBE.md](NAS_MCP_PROBE.md) |
| `22f46cad` | F1a: lokalna maszyna stanów checkpointów, zapis atomowy z blokadą, dokładny readback | CI 42655115320 — PASS |

**K1 — poprawione na `main`:** [commit `09bd668a`](https://github.com/elconcept/basic-memory-plugin/commit/09bd668af7b05ab9e0f6731bfc71e33e430ce19f) dodał jawny dispatch CI dla PR bota. Worker: [udany run 42652947577](https://github.com/elconcept/basic-memory-plugin/actions/runs/42652947577); CI: [udany run 42652997942](https://github.com/elconcept/basic-memory-plugin/actions/runs/42652997942) na SHA PR #3. PR #3 jest nadal draftem i nie został scalony.

**Wynik G4:** aktywny `/basic-memory-server` (1.0.0) udostępnia 12 narzędzi MCP. CLI, MCP i bieżące `config.json` wskazują jeden projekt `main`, zgodnie z wdrożeniem vanilla. Żadnych zmian bazy, reindeksacji, importu ani utworzenia nowych projektów.

**Ważne granice ukończenia:**
- T04: wygenerowano **kandydatów**, nie potwierdzono poprawnego OAuth i instalacji. Wariant OpenAI M jest testowy. Nie ma jeszcze aktywnego adaptera hooków.
- F1a: testy modułu `src/hooks/state_store.py` nie dowodzą integracji `PreCompact`, `SessionEnd`, `PostToolUse` ani testu ciągłości 6/6. **F1 pozostaje nieukończone.**
- `main` nadal synchronizuje źródła upstream do draft PR. Rozbudowany worker budowania i F9 znajdują się tylko na `impl/v1`, oczekują na weryfikację i merge zgodnie z bramkami.
- Obowiązuje zweryfikowany przez Claude [PLAN.md v1.2](PLAN.md), a nie usunięty draft. F0/G0, F1/F2, G4 i F11 pozostają osobnymi bramkami.

**Następne zadania:** F1b (samodzielny adapter eventów i bezpieczne przechwycenie transkryptów z fixture'ami), F2 (weryfikacja skilli `bm-checkpoint` i `bm-orient`, NOTICE/licencje), aktualizacja CI i odczytowy audyt brakujących projektów przed dalszym G4. Zero domyślnego przypisywania `null` do `main` lub `legal`.

## Korekta właściciela 1.3.1 (2026-11-09)

- **Bez zaplanowanej konserwacji.** Harmonogramy `cloudcli-cron`, cztery prompty konserwacyjne (`f33d11ea`, `d40ee1ba`) i bramka G7/F11 wycofane; `HOLYCLAUDE_SCHEDULED_PROMPTS.md` usunięty. To nie był pomysł ani decyzja użytkownika. Na holyclaude niczego nie aktywować.
- **Wdrożenie od razu.** Bez sondy `bm-probe`: plugin `basic-memory-nas` z `main` jest podpinany bezpośrednio do claude.ai i chatgpt.com (PLAN, decyzja właściciela 6).


## Kontynuacja implementacji — aktualny stan po wdrożeniu na main (2026-11-09)

**Ten blok zastępuje starsze fragmenty raportu mówiące, że main ma tylko draft PR lub nie posiada adaptera.** Raport zmian kodu i automatycznych testów NIE jest jeszcze dowodem instalacji pluginu u poszczególnych klientów.

| Zakres | Dowód |
|---|---|
| Parser transkryptu i materiały checkpointów | 93f45919, 1b6dfe12, 1e9d0f76; fixture testy są syntetyczne |
| Lokalna maszyna stanów i adapter zdarzeń | 06ec04dc, 0a9fe445, d85923df, f248ec54, 086ab000 |
| Pakowanie manifestu Claude z SessionStart, PreCompact, PostToolUse, PostToolUseFailure, Stop, SessionEnd | fa20eea1, 4079e325, c2857977 |
| Domyślny projekt vanilla main | fd3e0ef5, a645a80c |
| Materiał checkpointu wyłącznie dla przypisanego projektu | 5995cd55 |
| Zakotwiczone poprawki bm-checkpoint, bm-orient, memory-okf dla obu klientów | 8d5fa7d2, 5a2a479f, 68798779, f678154b, 696d6933 |
| Wygenerowane pliki hooków i skilli | PR #8 -> merge 00ef3f63 do impl/v1; commit a320bf79 na main |
| Scalenie kodu impl/v1 z main | 1f69007a |
| CI wymusza dokładną zgodność obu opublikowanych pakietów z upstreamem | 48f45016; zielony przebieg 42660857083 |

### Worker GitHub Actions — sprawdzony po integracji

- Harmonogram: **03:23 UTC codziennie** oraz ręczny workflow_dispatch.
- Obecna polityka planu 1.3.1: po testach aktualizacja bezpośrednio do main, bez draft PR; awaria -> jedno aktualizowane zgłoszenie.
- [Ręczny przebieg 42660609143](https://github.com/elconcept/basic-memory-plugin/actions/runs/42660609143): **SUCCESS**, w tym snapshot, testy, regeneracja i check obu artefaktów. SHA main pozostał bez zmian — brak nowych zmian upstream do commitowania.
- [CI 42660857083](https://github.com/elconcept/basic-memory-plugin/actions/runs/42660857083): **SUCCESS**; ścisła kontrola zgodności commitowanych pakietów z vendor/upstream.
- **Do dalszego pomiaru:** pierwszy przebieg automatyczny o zaplanowanej godzinie i pierwsza rzeczywista aktualizacja przy nowym SHA upstreamu. Udany ręczny run sam w sobie nie dowodzi wykonania harmonogramu.

### Otwarte bramki

- **CLIENT-VERIFIED:** GitHub CI i pliki w repo nie dowodzą załadowania pluginu do claude.ai, Claude Code, ChatGPT lub Codex. OAuth/MCP read/write/readback trzeba wykazać osobno na każdej platformie.
- **F1 / G1:** adapter przetestowano na fixture'ach syntetycznych. Brak rzeczywistych zanonimizowanych payloadów PostToolUse, PostToolUseFailure i realnego readback, oraz E2E ciągłości pamięci 6/6 (z kompakcją i bez).
- **F2:** w generatorze są zakotwiczone patche upstream; skille oraz mechanizm aktualizacji na klientach jeszcze nieprzetestowane.
- **Holyclaude:** plan 1.3.1 wycofał konserwację według harmonogramu. Zadań nie aktywowano. Zmiana ta jest sprzeczna z wcześniejszym wariantem planu i nie została automatycznie cofnięta.
- **NAS:** nie modyfikowano danych instancji Basic Memory; brak migracji i reindeksacji.

**Następne kroki:** dowód załadowania pluginu w Claude i ChatGPT, weryfikacja prawdziwego formatu odpowiedzi MCP, pełne E2E 6/6, dopiero potem formalne ukończenie F1 i wdrożenia.

## 2026-11-09 — v2.0.0: parytet z upstreamem

- Rdzeń `claude/` = 8 `bm-*` + `schemas/` + `output-styles/` + `.mcp.json` (NAS) + bezstanowy hook SessionStart.
- `claude-extras/` (oraz `openai-extras/`) = 16 `memory-*`, osobny plugin w marketplace.
- Usunięty silnik checkpointów i jego testy; patche `bm-checkpoint`/`bm-orient` usunięte; patche `bm-setup`/`bm-status` przepisane na MCP-only; usunięte z treści nazwy wewnętrzne (T05, nazwy hostów).
- Koszt listingu skilli rdzenia: ~2,1 tys. znaków (wcześniej ~5,4 tys. dla 24 skilli).
