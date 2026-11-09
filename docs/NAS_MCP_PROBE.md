# G4 — audyt odczytowy rzeczywistego CLI i MCP na NAS

**Data:** 2026-11-09  
**Status:** tożsamość projektów CLI/MCP w aktywnym kontenerze potwierdzona; rozbieżność wobec wcześniejszej listy oczekiwanych projektów **nierozstrzygnięta**.  
**Środowisko:** kontener `/basic-memory-server`, wersja CLI 1.0.0, połączenie FastMCP do `http://127.0.0.1:8000/mcp` **z wnętrza tego samego kontenera**. Bez zmiany konfiguracji, bazy ani plików.

## Fakty pomiarowe

- `/app/.venv/bin/basic-memory project list --json` wyświetla `main`.
- `bm_project(command="list")` przez działający serwer MCP zakończyło się bez błędu. Wynik zawiera `main`, a nie zawiera nazw `legal` ani `model-memory`.
- Konfiguracja aktywnego kontenera: `/home/appuser/.basic-memory/config.json` ma mapę `projects` z jednym kluczem `main`. Odczytano wyłącznie nazwy pól/kluczy i nazwy projektów; **nie** pobierano wartości poświadczeń, `database_url` ani sekretów do kontekstu modelu.
- `/proc/1/environ`: stwierdzono nazwy zmiennych `BASIC_MEMORY_DEFAULT_PROJECT`, `BASIC_MEMORY_HOME`, `BASIC_MEMORY_PROJECT_ROOT`, `BASIC_MEMORY_SYNC_CHANGES`, `BASIC_MEMORY_SYNC_DELAY`, `BASIC_MEMORY_LOG_LEVEL`; **wartości nie były wyświetlane**.
- Serwer udostępnia **12** narzędzi MCP: `bm_context`, `bm_delete`, `bm_edit`, `bm_find`, `bm_list`, `bm_man`, `bm_move`, `bm_project`, `bm_read`, `bm_schema`, `bm_search`, `bm_write`.

## Rozstrzygnięcie G4

Zgodność `CLI project list`, `MCP bm_project` i aktualnej konfiguracji kontenera oznacza, że **wcześniejsza rozbieżność CLI kontra działający MCP nie została wykazana**. Jednocześnie nadal istnieje sprzeczność z wcześniejszą deklarowaną listą projektów `main`, `legal`, `model-memory`. Obecny pomiar **nie dowodzi utraty danych** ani nie wyjaśnia, czy te nazwy dotyczą innej konfiguracji, poprzedniego wdrożenia lub odrębnej instancji.

**Wymagany STOP:** żadnej inicjalizacji brakujących nazw, żadnego `bm project create`, reindeksacji, czyszczenia, modyfikacji konfiguracji ani migracji przed rozstrzygnięciem tego rozbieżnego stanu. Funkcje `bm_man`, `bm_schema`, `bm_context` są wykryte, lecz nie zostały jeszcze poddane odrębnym testom funkcjonalnym.

## Następne czynności wyłącznie odczytowe

1. Porównać konfigurację i historię starego wdrożenia Basic Memory (jeśli istnieje), bez założenia, że projekt zniknął.
2. Zidentyfikować faktyczne ścieżki katalogów i wykryć inne pliki konfiguracji bez otwierania sekretów.
3. Dopiero po rozstrzygnięciu identyfikacji wykonać `/app/.venv/bin/basic-memory doctor --skip-self-test --json` w trybie bez zmian i porównać go z listą MCP.

Pomiar wykonany przez Portainer Docker Engine API w kontenerze; nie używano lokalnego Basic Memory na MacBooku.
