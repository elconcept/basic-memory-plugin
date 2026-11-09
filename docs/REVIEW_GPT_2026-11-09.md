# Recenzja GPT planu `basic-memory-nas` v1.1

**Data:** 2026-11-09  
**Dokument źródłowy:** [`docs/PLAN.md`](PLAN.md)  
**Charakter dokumentu:** uwagi recenzenta — **bez zmian w oryginalnym planie**.  
**Werdykt:** architektura nadaje się do realizacji, ale przed wdrożeniem produkcyjnym należy usunąć błędy P0 i doprecyzować testy. Samą fazę rozpoznawczą F0 można rozpocząć bez niszczenia dotychczasowej konfiguracji.

## Zakres oceny i skala

Ocena dotyczy spójności planu, semantyki checkpointów, odtwarzania wiedzy, izolacji projektów, bezpieczeństwa sekretów i bramek wdrożenia. Wnioski o możliwościach platform wymagają potwierdzenia na docelowych kontach/wersjach klienta: samo istnienie API w dokumentacji nie jest dowodem, że dana instalacja je otrzymuje.

- **P0 (blokujące):** możliwość utraty danych, przypisania ich do błędnego projektu lub fałszywego potwierdzenia zapisu.
- **P1 (przed odbiorem):** niezgodność wykonawcza, pominięty scenariusz lub niestabilny test.
- **P2 (utwardzenie):** jakość, automatyzacja i utrzymanie.

## P0 — wymagane poprawki

### R01. Nie oznaczać checkpointu jako `saved` na deklarację modelu
**Odniesienie:** G3, §7.4 `mark`, F8, D5; **priorytet: P0**.

Tryb G3-B przewiduje `bm_hook.py mark --status saved` z wywołania modelu. To obniża gwarancję N6: stan `saved` nie wynika wtedy z niezależnego potwierdzenia MCP.

**Propozycja:** G3 nadal testuje faktyczne przekazywanie zdarzeń `PreCompact`, `SessionStart`, `PostToolUse` i `Stop` dla właściwej wersji Codex. Brak eventu nie daje prawa do pominięcia kontroli. Przy ograniczeniu platformy wpis pozostaje `pending`/`failed`; ewentualny `mark` może co najwyżej oznaczać `reported_by_model`, nie `saved`. Mechanizm alternatywnego potwierdzenia wymaga odczytu odpowiedzi MCP przez zaufany komponent i odrębnego testu.

**Akceptacja:** zasymulowana fałszywa deklaracja modelu nigdy nie podnosi stanu do `saved`.

### R02. Izolować checkpointy o nieustalonym projekcie
**Odniesienie:** N8, §7.3–7.4 `session-start`, F5; **priorytet: P0**.

Warunek ponowienia `project == primaryProject or project == null` umożliwia przeniesienie nieprzypisanego checkpointu do kontekstu dowolnej sesji, w tym między `legal` i `main`.

**Propozycja:** wprowadzić stan `unassigned` (albo odrębny znacznik wymagający jawnego rozstrzygnięcia). Nie przypisywać projektu na podstawie aktualnej sesji. Wybór projektu musi wiązać konkretny `ck` z konkretnym projektem, a `bm_write`/`bm_edit`/`bm_read` mają otrzymywać jawny projekt.

**Akceptacja:** checkpoint bez projektu nie jest automatycznie zapisywany ani ponawiany w innym projekcie; test macierzy `legal` × `main` × `null`.

### R03. Potwierdzać tożsamość notatki, a nie samą obecność tekstu `ck`
**Odniesienie:** D5, §7.4 `post-tool`, §7.5; **priorytet: P0**.

Reguła „`bm_read` zawiera `ck`” może potwierdzić niepowiązaną odpowiedź albo odpowiedź z błędem. Nie wystarcza wyszukiwanie dowolnego identyfikatora w tekście wyniku zapisu.

**Propozycja:** po `bm_write`/`bm_edit` zapisać zweryfikowany identyfikator/ref notatki oraz projekt; wykonać `bm_read` dokładnie tej notatki; sprawdzić brak błędu, zgodność ref, projektu i `checkpoint_key` w treści. Przy ponowieniu stosować idempotentne wyszukanie i aktualizację z ochroną przed nadpisaniem równoległej zmiany, jeżeli API ją oferuje. Rozróżniać brak potwierdzenia i rzeczywisty błąd.

**Akceptacja:** odczyt innej notatki z tym samym fragmentem tekstu, błędny projekt, pusta odpowiedź lub błąd MCP nie dają stanu `saved`.

### R04. Zachować decyzje z całej sesji, a nie tylko wycinek wypowiedzi
**Odniesienie:** §7.4 `pre-compact`, F1, F10; **priorytet: P0**.

Limit 49 152 bajtów i kolejność priorytetów w materiale checkpointu mogą pomijać wczesne decyzje podjęte przez asystenta. Rejestr wywołań narzędzi nie zastępuje wniosków, uzasadnień i wyników.

**Propozycja:** dodatkowy trwały dziennik decyzji/ustaleń aktualizowany w trakcie pracy, z priorytetem w checkpoincie. Uwzględniać wyniki weryfikacji, ścieżki plików, SHA commitów, PR i następne kroki. Zachowywać informację o liczbie i rodzaju pominiętych pozycji; nie deklarować kompletności przy obcięciu. Dopuszczalne jest dzielenie materiału na kilka notatek, jeżeli pojedyncza przekracza limit.

**Akceptacja:** w F10 wszystkie decyzje, w tym wyłącznie z wczesnych odpowiedzi asystenta, trafiają do materiału, notatki oraz odtworzonej nowej sesji.

### R05. Obsłużyć brak lub awarię przechwycenia transkryptu
**Odniesienie:** §7.3–7.4, F1, F8; **priorytet: P0**.

W planie jest tolerancja uszkodzonych linii, lecz nie pełna semantyka braku `transcript_path`, nieczytelności pliku, nieznanego formatu, błędu zapisu lokalnego i błędnego ustalenia granicy kompakcji.

**Propozycja:** osobny stan `capture_failed`, diagnostyka z przyczyną, brak cichego sukcesu, bezpieczne ponowienie. Rozdzielić zachowanie Claude i Codex tam, gdzie hook przed kompakcją nie może zatrzymać operacji. Parser transkryptu traktować jako zależność testowaną fixture'ami rzeczywistych wersji klientów, z fikcyjnymi treściami.

**Akceptacja:** testy negatywne wszystkich pięciu awarii, bez utraty informacji o checkpointach.

### R06. Nie wystawiać surowych sekretów Docker API do kontekstu modelu
**Odniesienie:** G4, §8.3, §12; **priorytet: P0**.

Odczyt pełnego `Config.Env` i późniejsze filtrowanie po stronie modelu nadal może ujawnić sekrety w wyniku narzędzia.

**Propozycja:** w zaufanym wykonawcy przed zwróceniem wyniku ujawnić wyłącznie **nazwy** zmiennych, redagować mounty i logi błędów. Żadne wartości `Config.Env` ani nagłówki autoryzacyjne nie przechodzą do modelu, raportu i CI.

**Akceptacja:** test z przykładowym poświadczeniem nie pozwala mu dotrzeć do odpowiedzi narzędzia ani artefaktów.

## P1 — poprawki wykonawcze

### R07. Dodać utrwalanie na końcu sesji bez kompakcji
**Odniesienie:** D5, F10; **priorytet: P1**.

Sesja może zakończyć się bez `PreCompact`, więc plan nie gwarantuje powstania checkpointu. Rozważyć niezależny zapis ważnych decyzji w czasie sesji oraz lokalny checkpoint `SessionEnd` w środowiskach, które obsługują to zdarzenie. Nie opierać bezpieczeństwa wyłącznie na `SessionEnd` (awaria procesu może je ominąć).

**Akceptacja:** nowe kryterium F10: sześć decyzji, zamknięcie bez kompakcji, nowa sesja i odtworzenie 6/6.

### R08. Rozdzielić profile buildów Claude i OpenAI
**Odniesienie:** G0-O-X, §6.1–6.2, F0–F3; **priorytet: P1**.

G0-O-X pozwala wstrzymać OpenAI i kontynuować Claude; build równocześnie wymaga `openai_variant` i `openai_app_id`, które w tym wyniku pozostają `null`.

**Propozycja:** `build.py --target claude|openai|all`, niezależne warunki walidacji i CI; `all` dopiero po zaliczeniu bramek obu platform.

**Akceptacja:** pełny build/CI `claude` działa przy `openai_variant=null`, bez generowania fałszywej konfiguracji OpenAI.

### R09. Osobno mapować natywne skille Claude i Codex
**Odniesienie:** D3, §6.2, §7.1–7.2; **priorytet: P1**.

Plan kopiuje `bm-*` z katalogu Claude do obu artefaktów, mimo istnienia upstreamowego wariantu Codex. Różnice host-specyficzne wymagają audytu przed ujednoliceniem.

**Propozycja:** wspólne `memory-*` z jednego źródła, `bm-*` dobierane osobno dla Claude i Codex; nakładać wspólne patche semantyczne. Liczbę skilli i walidację prowadzić dla każdego artefaktu z osobna.

**Akceptacja:** lista różnic `bm-*` i test zgodności zachowania checkpointu, orientacji i statusu na obu klientach.

### R10. Obsłużyć `PostToolUseFailure` w Claude Code
**Odniesienie:** §7.1, §7.4, F1; **priorytet: P1**.

Plan przewiduje tylko `PostToolUse`, a błędne wywołania mogą przechodzić oddzielną ścieżką zdarzeń.

**Propozycja:** rozpoznać i podłączyć `PostToolUseFailure` zgodnie z wersją klienta. Dla błędów `bm_write`, `bm_edit`, `bm_read` zachować stan i przyczynę, bez pozornego potwierdzenia.

**Akceptacja:** symulowana awaria MCP jest odnotowana, a `SessionStart` ponawia niezakończony checkpoint.

### R11. Urealnić ograniczenia uprawnień ChatGPT i dziedziczenia OAuth
**Odniesienie:** G0-O, G1, F7–F8; **priorytet: P1**.

Rozdzielić: widoczność skilli, rejestrację pluginu, rzeczywiste działanie MCP z zapisem oraz możliwość użycia MCP w Codex bez osobnego logowania. Nie traktować tych cech jako jednego potwierdzenia.

**Propozycja:** w G0-O wymagać oddzielnych wyników `bm_project`, `bm_write`, `bm_read`, widoczności skilli w web, widoczności w Codex, działania po restarcie, braku duplikatów i braku dodatkowej autoryzacji. Niedostępność funkcji w planie konta należy raportować jako ograniczenie platformy, nie błąd serwera NAS.

**Akceptacja:** wszystkie wymienione testy mają osobny zapis wyniku i dowodu w `VERIFICATION.md`.

### R12. Weryfikować bezpieczeństwo Cloudflare OAuth na serwerze
**Odniesienie:** §10, G0; **priorytet: P1**.

Obok testu samego OAuth sprawdzić metadane discovery, redirect/callback, dynamiczną rejestrację klienta, poprawną odpowiedź `401` na brak autoryzacji, obsługę zasobu OAuth i serwerową walidację tokenu/JWT. Nie wymaga to automatycznej zmiany polityki Cloudflare.

**Akceptacja:** poprawny klient działa, klient bez autoryzacji nie uzyskuje narzędzi, błędny/nieprzeznaczony token jest odrzucany.

### R13. Utwardzić scenariusze odbioru i aktualizacji
**Odniesienie:** §6.3, §9, F9–F10; **priorytet: P1/P2**.

1. W G6 sprawdzać wykonanie hooków i ewentualne ponowne zatwierdzenie zaufania po zmianie wersji, nie tylko widoczność nowego pluginu.
2. Testy skanowania sekretów uruchamiać na bieżących plikach **i historii Git**, z minimalnymi wyjątkami.
3. Notatki testowe usuwać wyłącznie po identyfikatorach utworzonych w danym teście; nie usuwać szerokim wzorcem ani całego folderu.
4. Dodać testy: dwa jednoczesne checkpointy, błąd dysku, utrata OAuth, rozłączenie w połowie zapisu, dwie kompakcje, zmiana projektu i zakończenie sesji bez kompakcji.
5. W F10 osobno raportować utratę informacji na etapach: transkrypt → materiał → MCP → notatka → odtworzenie.

**Akceptacja:** raport F10 identyfikuje etap utraty danych i nie oznacza wdrożenia jako udane przy 5/6 decyzji.

## Co zachować bez zasadniczych zmian

- **D1 / N7:** jedno repo, osobne artefakty, upstream wyłącznie przez PR, brak auto-merge.
- **N2 / N5:** zero sekretów i połączeń sieciowych w lokalnych hookach.
- **N3 / N4:** brak zduplikowanych skilli i połączeń MCP.
- **N8:** jawny wybór projektu, po korekcie obsługi `null` opisanej w R02.
- **N9:** kopie istniejących konfiguracji przed czyszczeniem.
- **F0 / G0–G6:** bramki weryfikacyjne zamiast założeń o środowisku.
- **F10:** test odtwarzania decyzji jako nadrzędne kryterium odbioru, rozszerzony o R04/R07/R13.

## Kolejność nanoszenia poprawek do przyszłej v1.2

1. **Przed F1:** R02, R03, R04, R05, R06 — invarianty bezpieczeństwa i ciągłości pamięci.
2. **Przed F2–F3:** R08, R09, R10 oraz wybór rzeczywistego trybu Codex (R01).
3. **W ramach F0 i integracji:** R11, R12.
4. **Przed F10:** R07 i R13.
5. **Po zmianach:** pełny test regresji, brak automatycznego merge i oddzielne potwierdzenie ograniczeń poszczególnych platform.

**Decyzja recenzenta:** zatwierdzam kierunek architektoniczny; nie zatwierdzam v1.1 do bezwarunkowego wdrożenia. F0 można przeprowadzić w trybie odczytowym/sondującym, ale bez kasowania konfiguracji i przełączenia działających klientów. Ta recenzja jest osobnym dokumentem; plan użytkownika w `docs/PLAN.md` pozostaje nietknięty.

## Dokumentacja do weryfikacji przy wykonaniu

- [Claude Code — hooks](https://code.claude.com/docs/en/hooks)
- [Claude Code — plugins reference](https://code.claude.com/docs/en/plugins-reference)
- [OpenAI — plugins](https://developers.openai.com/plugins/build/plugins)
- [OpenAI — Codex MCP](https://developers.openai.com/codex/mcp)
- [Basic Memory upstream](https://github.com/basicmachines-co/basic-memory)
