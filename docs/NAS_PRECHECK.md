# NAS — wstępny odczyt Basic Memory (G0-NAS, bez modyfikacji)

**Data:** 2026-11-09  
**Zadanie:** T09-preflight (częściowe)  
**Status:** PARTIAL / STOP przed naprawami.

## Dane bezpośrednio sprawdzone

- Portainer environment `local` (ID 3) udostępnia kontener `/basic-memory-server`, stan: `running`, obraz: `ghcr.io/basicmachines-co/basic-memory:latest`.
- Kontener uruchamia `basic-memory mcp --transport streamable-http --host 0.0.0.0 --port 8000`; użytkownik procesu skonfigurowany jako `appuser`.
- Montowania: `/volume2/@docker/volumes/basic-memory_basic-memory-config/_data` → `/home/appuser/.basic-memory` oraz `/volume2/docker/basic-memory-data/knowledge` → `/app/data`, oba RW. To informacja diagnostyczna o dostępnych montowaniach, **bez odczytu ich treści**.
- `basic-memory --version` **bez ścieżki absolutnej** zwraca `command not found` w zwykłym `docker exec sh`.
- `/app/.venv/bin/basic-memory --version` działa i zwraca **1.0.0**. Python systemowy `/usr/local/bin/python3` nie widzi metadanych pakietu; właściwa instalacja jest w `/app/.venv`.
- `/app/.venv/bin/basic-memory project list --json` zwrócił **jeden projekt: `main`**, `local_path=/basic-memory`, `is_default=true`.
- **Nie** sprawdzono jeszcze `bm_project` przez właściwy endpoint MCP i nie ustalono tożsamości bazy CLI/MCP. Wcześniejszy plan wymieniał `main`, `legal`, `model-memory`; tej rozbieżności **nie wolno** interpretować jako utraty danych ani naprawiać bez dalszej diagnostyki.
- Nie wykonywano restartu, instalacji, zmian migracji, modyfikacji bazy ani usuwania danych.

## Wnioski wykonawcze dla v1.2

1. W G4 i `memory-doctor` używać **bezwzględnej ścieżki CLI** `/app/.venv/bin/basic-memory` lub sprawdzonego odpowiednika z aktywnego obrazu. Nie zakładać obecności binarki w `PATH` interaktywnego `docker exec`.
2. Porównać listę CLI z `bm_project` w **tym samym działającym kontenerze** i tą samą konfiguracją. Przy rozbieżności STOP — nie diagnozować ani naprawiać indeksu niewłaściwego środowiska.
3. Dopiero potem uruchomić read-only `doctor --skip-self-test --json`, z kontrolą wartościowej diagnostyki i bez ujawniania sekretów.
4. Każdy import, `reindex` i operacja zapisu pozostają poza zakresem preflight.

## Stan pozostałych bramek

| Bramka | Wynik |
|---|---|
| Kontener działa i obraz potwierdzony | PASS |
| CLI dostępne w obrazie | PASS, tylko przez `/app/.venv/bin/basic-memory` |
| CLI wersja 1.0.0 | PASS |
| Lista projektów CLI | PASS, widoczne wyłącznie `main` |
| Identyczność CLI z MCP i projektami użytkownika | PENDING |
| `doctor` read-only | PENDING |
| Import, schema, benchmark polskich zapytań | PENDING |

**Zasada:** pojedynczy wynik CLI jest obserwacją dotyczącą tego procesu i konfiguracji, nie dowodem braku innych projektów lub utraty danych.
