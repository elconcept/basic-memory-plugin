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
- `cloudcli-cron` **v0.2.0** jest zainstalowany w CloudCLI; istnieje katalog stanu schedulera; liczba ledgerów `*.json`: **0**.
- Lokalny scheduled prompt możliwy po aktywacji w UI i konfiguracji procesu `claude`; odrębny od chmurowego Claude `/schedule`.
- Cztery gotowe, ograniczone do projektu `main` prompty w [HOLYCLAUDE_SCHEDULED_PROMPTS.md](HOLYCLAUDE_SCHEDULED_PROMPTS.md). **Nie ustawiono jeszcze aktywnych terminów.** Najpierw instalacja właściwego `basic-memory-nas` na kliencie, test `Run Now`, autoryzacja i rzeczywisty MCP readback.
- Plugin `cloudcli-cron` v0.2.0 nie wspiera `biweekly`; defrag zaproponowany tygodniowo lub miesięcznie w trybie proposal-only.

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

## Nieukończone etapy (dla następnego modelu)

1. **Claude review** PR #4: rygorystyczny audyt upstreama, schedulera i licencji; dopiero potem zmiana DRAFT → APPROVED.
2. **G0 Platform**: Claude/ChatGPT/Codex OAuth i plugin-distribution; osobny dowód dla narzędzi write/readback i dziedziczenia autoryzacji.
3. **T04 artefakty**: generator `claude/` oraz `openai/`, budowanie profilami, licencja i skille natywne klienta; obecny sync jest tylko snapshotem.
4. **T05 checkpoint state machine** oraz sesja bez kompakcji; testy negatywne przed migracją.
5. **T06 skille/setup** i dopiero później **T08** scheduled prompts w HolyClaude.
6. **T09** identyczność CLI/MCP, `bm_man`, schema, doktor i import; żadnych napraw bez wcześniejszej zgody.
7. **T10** end-to-end 6/6 z dwóch niezależnych sesji; dopiero wtedy propozycja merge do main.

Nie wolno opisywać `cloudcli-cron` jako aktywnego harmonogramu utrzymania pamięci ani snapshot PR #3 jako zaktualizowanego pluginu: oba mają jeszcze niezrealizowane bramki.

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
- `cloudcli-cron` w HolyClaude jest zainstalowany, ale cztery harmonogramy nie są jeszcze włączone. Przed ich aktywacją wymagane są F5, rzeczywisty dostęp MCP i wymuszona konfiguracją polityka read-only.
- Obowiązuje zweryfikowany przez Claude [PLAN.md v1.2](PLAN.md), a nie usunięty draft. F0/G0, F1/F2, G4 i F11 pozostają osobnymi bramkami.

**Następne zadania:** F1b (samodzielny adapter eventów i bezpieczne przechwycenie transkryptów z fixture'ami), F2 (weryfikacja skilli `bm-checkpoint` i `bm-orient`, NOTICE/licencje), aktualizacja CI i odczytowy audyt brakujących projektów przed dalszym G4. Zero domyślnego przypisywania `null` do `main` lub `legal`.
