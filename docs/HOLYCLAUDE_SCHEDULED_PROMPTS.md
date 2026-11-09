# Holyclaude — Scheduled Prompt: wdrożenie konserwacji Basic Memory

**Task:** T06 (przygotowanie operacyjne; **nie aktywuje** harmonogramów).  
**Stan z audytu NAS 2026-11-09:** w kontenerze `/Holyclaude` (image `coderluii/holyclaude:latest`) katalog `/home/claude/.claude-code-ui/plugins/cloudcli-cron` istnieje. `package.json` i `manifest.json` zgłaszają **v0.2.0**. `/home/claude/.cloudcli-workspace-scheduled-prompts` istnieje, ale liczba plików ledger `*.json` wynosi **0**. Jest to weryfikacja instalacji, **nie** aktywnego schedule i nie test działania MCP. Nie wyświetlano ani nie modyfikowano tokenów ani konfiguracji kont.

**Źródło upstream:** [grostim/cloudcli-cron](https://github.com/grostim/cloudcli-cron). Plugin jest lokalny: uruchamia nowe procesy CLI w katalogu workspace, zapisuje harmonogram i historię wykonania, wspiera daily/weekdays/weekly/monthly, Run Now, Pause/Resume, Retry. Nie wspiera własnej składni cron ani natywnego „co dwa tygodnie”.

## Rozróżnienie, które musi sprawdzić Claude

- `cloudcli-cron` w HolyClaude: **lokalny scheduled prompt** działający wewnątrz kontenera, używający zainstalowanego CLI i autoryzacji tego kontenera. Właściwy mechanizm dla tego zadania.
- `/loop` Claude Code: sesja lokalna, ograniczona czasowo, nie nadaje się na trwały scheduler.
- `/schedule` Claude Code: **cloud routine** w infrastrukturze Anthropic, a nie automatycznie zadanie wewnątrz kontenera HolyClaude.
- DSM Task Scheduler: **wyłączony z architektury** na życzenie użytkownika.

## Bramka G0-Holyclaude

1. Upewnić się, że plugin `cloudcli-cron` jest aktywny w CloudCLI UI (`Settings → Plugins`); obecność katalogu nie wystarcza.
2. Zweryfikować `Claude Code` preset: binarka `claude` w kontenerze, proces uruchamiany w wybranym workspace, konfiguracja autoryzacji i dostęp do MCP `bm.xlap.pl` przez plugin `basic-memory-nas`. **Nie** przyjmować, że nowy proces CLI dziedziczy autoryzację z otwartej sesji.
3. Utworzyć osobny **testowy** workspace, projekt Basic Memory testowy. Nie używać `legal` ani `main` dla pierwszego testu zapisu.
4. Skonfigurować próbny prompt tylko do odczytu, kliknąć **Run Now**, sprawdzić historię, status procesu i odczyt przez `bm_project` + `bm_search`.
5. Następny test z jedną syntetyczną notatką testową `bm_write` + `bm_read`. Zapisać dowód odczytu z właściwego projektu; po testach usunąć wyłącznie tę notatkę z identyfikatorem testowym.
6. Dopiero po zaliczeniu włączyć cztery schedule poniżej, każdemu przypisując **jawny projekt `main`**. Dla `legal` stworzyć osobny zestaw tylko na wyraźne zlecenie i po ocenie ryzyk. Nie uruchamiać jednego promptu w wielu projektach.
7. Zapis konfiguracji tylko przez obsługiwany UI/API pluginu. Nie edytować ręcznie prywatnych ledgerów JSON.
8. Po pierwszym zaplanowanym wykonaniu porównać status `succeeded` z rzeczywistym wynikiem MCP. Sam exit code 0 nie wystarcza do twierdzenia, że notatki zostały zapisane.

## Cztery prompty do wprowadzenia w UI CloudCLI (projekt main)

Działania konserwacyjne dotyczą **wyłącznie repozytorium wiedzy Basic Memory projektu main**. Nie wykonywać wyszukiwania lub zapisu w `legal`. Wszelkie automatyczne operacje modyfikujące ważną wiedzę powinny być wyłączone do czasu zatwierdzenia polityki.

### 1. Daily — memory-reflect

- Nazwa: `BM main — reflect`
- Częstotliwość: daily, 02:20, timezone skonfigurowany/zweryfikowany w CloudCLI
- Docelowy skill: `basic-memory-nas:memory-reflect`

~~~text
Use the basic-memory-nas:memory-reflect skill with Basic Memory project explicitly set to "main".
1) Confirm the active MCP server and that bm_project lists "main"; if missing, stop and report FAILURE.
2) Search only project "main" for recently added or changed notes, open tasks and durable decisions.
3) Summarize new durable facts, unresolved questions and potentially contradictory claims WITH references to exact notes.
4) Draft a dated reflection note only when bm_write and bm_read are available and the write is explicitly permitted under the configured policy; otherwise deliver a proposal without changing the knowledge base.
5) Do not access project "legal", do not delete, merge, overwrite locked notes, or silently reinterpret source material.
6) Return a short report: read count, note references, proposed actions, write/readback result, error status.
~~~

### 2. Weekly — memory-curate

- Nazwa: `BM main — curate`
- Częstotliwość: weekly, Monday 02:45
- Docelowy skill: `basic-memory-nas:memory-curate`

~~~text
Use basic-memory-nas:memory-curate for Basic Memory project "main" only.
Read graph relationships and find orphan notes, duplicate candidates, missing relations, and conflicting metadata. Produce a ranked curation proposal with exact note IDs and reasons. Do not merge, delete, rewrite or cross-copy anything automatically. Any new curated index or relationship must be proposed for approval first. Return auditable links and status; treat failure to fetch as FAILURE, not as "nothing to curate".
~~~

### 3. Weekly (rather than unsupported biweekly) — memory-defrag

- Nazwa: `BM main — defrag proposal`
- Częstotliwość: weekly, Sunday 03:10; **proposal-only**; choose monthly as alternative if weekly is too frequent
- Docelowy skill: `basic-memory-nas:memory-defrag`

~~~text
Use basic-memory-nas:memory-defrag in proposal-only mode for project "main". Identify bloated notes, repeated fragments, contradictory or stale summaries. First write a proposed transformation plan with before/after note IDs, evidence and risks; do not perform any destructive or semantic change, archive, deletion, or merge. Ensure that even proposed transformations preserve provenance and the original meaning. Report the plan for user approval. Project "legal" is out of scope.
~~~

### 4. Weekly — memory-lifecycle

- Nazwa: `BM main — lifecycle review`
- Częstotliwość: weekly, Wednesday 02:50
- Docelowy skill: `basic-memory-nas:memory-lifecycle`

~~~text
Use basic-memory-nas:memory-lifecycle in project "main" only. Inspect active/completed tasks and notes with explicit status metadata. Recommend archive/status changes with exact note IDs, evidence, and the reason each transition is justified. Do not automatically move, archive, delete, or rewrite notes. If the project lacks a lifecycle schema or status metadata, report that issue rather than inventing statuses. Return a concise pending-action list.
~~~

## Warunki aktywacji

- `basic-memory-nas` jest zainstalowany w nowym procesie `claude` na HolyClaude;
- `G0-Holyclaude` (read i write/readback w teście) zakończony;
- polityka zgód na zapisy ustalona; w pierwszej iteracji wszystkie propozycje curator/defrag/lifecycle są **read-only**;
- udokumentowany status zadania w `docs/VERIFICATION.md` z metadanymi, **bez treści prywatnych notatek, sekretów i tokenów**;
- monitorowanie `failed`/`missed` z rejestrem wykonania CloudCLI.

## Kryterium odbioru

Są widoczne cztery zapisane schedule o jawnych projektach, wtyczka podaje kolejne terminy, testowy `Run Now` kończy się rzeczywistym odczytem MCP, a pierwszy samodzielny scheduled run zostawia wynik i log. Do czasu spełnienia tych kryteriów status to `PENDING`, niezależnie od obecności skryptów lub katalogu pluginu.
