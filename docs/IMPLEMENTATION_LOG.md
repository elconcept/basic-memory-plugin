# Basic Memory NAS — stan wdrożenia i trwałe checkpointy

**Ostatnia aktualizacja:** 2026-11-09. **Branch implementacji:** `impl/v1`.  
**Plan do recenzji:** [PLAN_v1.2_DRAFT.md](PLAN_v1.2_DRAFT.md)  
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

## Nieukończone etapy (dla następnego modelu)

1. **Claude review** PR #4: rygorystyczny audyt upstreama, schedulera i licencji; dopiero potem zmiana DRAFT → APPROVED.
2. **G0 Platform**: Claude/ChatGPT/Codex OAuth i plugin-distribution; osobny dowód dla narzędzi write/readback i dziedziczenia autoryzacji.
3. **T04 artefakty**: generator `claude/` oraz `openai/`, budowanie profilami, licencja i skille natywne klienta; obecny sync jest tylko snapshotem.
4. **T05 checkpoint state machine** oraz sesja bez kompakcji; testy negatywne przed migracją.
5. **T06 skille/setup** i dopiero później **T08** scheduled prompts w HolyClaude.
6. **T09** identyczność CLI/MCP, `bm_man`, schema, doktor i import; żadnych napraw bez wcześniejszej zgody.
7. **T10** end-to-end 6/6 z dwóch niezależnych sesji; dopiero wtedy propozycja merge do main.

Nie wolno opisywać `cloudcli-cron` jako aktywnego harmonogramu utrzymania pamięci ani snapshot PR #3 jako zaktualizowanego pluginu: oba mają jeszcze niezrealizowane bramki.
