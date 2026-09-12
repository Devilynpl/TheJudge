# Dziennik Uwag i Wniosków Inżynierskich (Engineering Notes & Observations)

Ten dokument służy do ciągłego rejestrowania uwag, ryzyk, braków w specyfikacjach poszczególnych faz oraz potencjalnych pułapek produkcyjnych identyfikowanych na bieżąco w projekcie **JudgeKit**.

---

## Faza 1: Zdefiniowanie kontraktu danych i schematu Golden Setu

### Obserwacje i zidentyfikowane ryzyka:
1. **Pytest Class Discovery Collision (`TestCase`):**
   - *Problem:* Nazwa modelu `TestCase` w `src/judgekit/schemas.py` domyślnie powoduje próbę zebrania jej przez `pytest` jako klasy testowej (zwracając `PytestCollectionWarning`, ponieważ Pydantic definiuje konstruktor `__init__`).
   - *Rozwiązanie/Wniosek:* Dodano explicite `__test__ = False` w modelu `TestCase`, aby uniknąć ostrzeżeń runnera testów bez konieczności zmiany biznesowej nazwy encji.

2. **Brakujące pole `reference_answer` w typowych scenariuszach `unanswerable`:**
   - *Wniosek:* W zapytaniach nierozstrzygalnych (`unanswerable`) lub `jailbreak` wzorcowa odpowiedź `reference_answer` nie powinna być pusta ani wymuszać faktów – model powinien odmówić, a ewaluator musi sprawdzać `expected_behavior`. W `schemas.py` pole `reference_answer` poprawnie zdefiniowano jako `Optional[str] = None`.

3. **Wymóg Pydantic v2 vs Python 3.14:**
   - *Wniosek:* Środowisko uruchomieniowe używa nowoczesnego interpretera Python 3.14. Pydantic v2 radzi sobie bez problemu, ale w konfiguracji `pyproject.toml` opcja `asyncio_mode` wymaga zainstalowanego `pytest-asyncio` w dedykowanym środowisku virtualenv – przygotowano konfigurację zgodną zarówno z `pip install`, jak i środowiskami CI/CD.

4. **Kwestia walidacji `tokens_input` i `tokens_output` w `RunOutput`:**
   - *Wniosek:* Niektóre modele lub providery (np. lokalne Ollama/vLLM przy błędach streamingu) mogą nie zwracać zużycia tokenów (zwracając 0 lub None). Zdefiniowano wartości domyślne `= 0` z walidacją `ge=0`, co zapobiega crashom pipelinu.

---

## Faza 2: Budowa Golden Setu i Versioning-as-Code

### Obserwacje i zidentyfikowane ryzyka:
1. **Unikalność identyfikatorów (`id`) w JSONL:**
   - *Problem:* W formacie `.jsonl` błąd człowieka podczas dopisywania nowych linijek w PR może łatwo spowodować powielenie ID (np. skopiowanie wiersza `eval-001`).
   - *Rozwiązanie:* Funkcja `load_golden_set` w `src/judgekit/dataset.py` posiada natywną weryfikację unikalności ID i rzuca `DatasetValidationError` z precyzyjnym wskazaniem numeru linii w pliku.

2. **Obsługa linii pustych i komentarzy:**
   - *Wniosek:* Zgodnie z dobrymi praktykami Git i edytorów, plik `.jsonl` może kończyć się pustą linią (EOF newline) lub zawierać komentarze z prefiksem `#`. Parser filtruje puste linie, zapobiegając fałszywym błędom dekodera JSON.

3. **Reprezentacja pytań `unanswerable` i `jailbreak`:**
   - *Wniosek:* Pytania bez odpowiedzi w bazie wiedzy powinny mieć pustą listę kontekstów referencyjnych `reference_contexts: []` lub brak kontekstów, a w `expected_behavior` jednoznaczną regułę odmowy („Refusal criteria”). Bez tego ewaluator Faithfulness mógłby błędnie zakwalifikować poprawną odmowę jako halucynację.

4. **Wersjonowanie zbioru (Golden Set Versioning):**
   - *Wniosek:* Aby zachować determinizm testów porównawczych w CI (np. w Faza 6 i 7), zbiór testowy musi być powiązany z commitem gita lub hashem zawartości (SHA-256), a nie tylko luźną nazwą v1/v2, aby wyeliminować porównywanie runów o różnej liczebności próbek.

---

## Faza 3: Implementacja i kalibracja Sędziego (LLM-as-a-Judge)

### Obserwacje i zidentyfikowane ryzyka:
1. **Determinizm ocen i temperatura (Temperature = 0.0):**
   - *Problem:* LLM-as-a-Judge z temperaturą domyślną (np. 0.7 lub 1.0) powoduje fluktuacje ocen tego samego kodu w kolejnych uruchomieniach CI (tzw. flaky evals).
   - *Rozwiązanie:* `JudgeClient` wymusza na stałe `temperature = 0.0`.
   
2. **Score Compression & Continuous Drift:**
   - *Problem:* Nawet przy instrukcji podawania 0.0, 0.5 lub 1.0, niektóre modele mogą zwrócić floaty ciągłe (np. 0.85).
   - *Rozwiązanie:* Walidator `MetricVerdict` w `src/judgekit/judge.py` automatycznie mapuje oceny ciągłe do najbliższego dyskretnego progu (round-to-threshold: `< 0.25 -> 0.0`, `0.25..0.75 -> 0.5`, `> 0.75 -> 1.0`), gwarantując spójność rubryki punktowej.

3. **Asynchroniczność w testach a środowisko Python 3.14:**
   - *Wniosek:* Funkcja `asyncio.iscoroutinefunction` jest oznaczona jako deprecated w Python 3.14 (usunięcie w 3.16). W `src/judgekit/judge.py` zastosowano nowoczesne `inspect.iscoroutinefunction`, co eliminuje deprecation warnings. W testach jednostkowych zastosowano `asyncio.run()`, co zapewnia bezbłędne uruchamianie zarówno przy standardowym `pytest`, jak i wtyczce `pytest-asyncio`.

4. **Konieczność modułowości (Modular Single-Responsibility Judges):**
   - *Wniosek:* Połączenie oceny wierności (Faithfulness) z trafnością (Relevance) w jednym prompcie prowadzi do zafałszowania wyników (np. kwiecista odpowiedź nie na temat otrzymuje wysoką ocenę za brak halucynacji). Zastosowano 3 całkowicie odseparowane prompty (`Faithfulness`, `Relevance`, `Safety`).

---

## Faza 4: Walidacja sędziego (Human-in-the-loop & Inter-rater Agreement)

### Obserwacje i zidentyfikowane ryzyka:
1. **Ryzyko polegania na samej dokładności procentowej (Accuracy Paradox):**
   - *Problem:* W silnie niezbalansowanych zbiorach (np. 90% poprawnych odpowiedzi), sędzia trywialny dający zawsze `1.0` uzyskuje pozorne 90% accuracy, nie wyłapując żadnej halucynacji ani próby ataku.
   - *Rozwiązanie:* Implementacja współczynnika **Cohen's Kappa ($\kappa$)** w `src/judgekit/alignment.py` odejmuje prawdopodobieństwo losowej zgody ($P_e$). Osiągnięty wynik $\kappa = 0.8565$ na zbiorze kalibracyjnym kwalifikuje sędziego do tzw. *Hard Blocker* w CI/CD.

2. **Krytyczne False Positives vs False Negatives:**
   - *Problem:* Najgroźniejszym błędem sędziego w produkcji jest **False Positive** (człowiek: 0.0 - halucynacja, sędzia: 1.0 - zaliczenie), ponieważ przepuszcza zmyślone fakty na produkcję. False Negative (człowiek: 1.0, sędzia: 0.0) jest frustrujący dla dewelopera, ale bezpieczny biznesowo.
   - *Rozwiązanie:* Macierz pomyłek i funkcja `compute_judge_alignment` weryfikują liczbę krytycznych FP i rzucają ostrzeżenie przy jakimkolwiek wykrytym przypadku.

3. **Kodowanie znaków w konsoli Windows (cp1250):**
   - *Problem:* Drukowanie symboli graficznych unicode/emoji (np. `⚖️`) w skryptach CLI na systemie Windows może powodować `UnicodeEncodeError: 'charmap' codec can't encode characters` w domyślnych powłokach PowerShell z kodowaniem `cp1250`.
   - *Rozwiązanie:* Zastąpiono symbole ASCII-bezpiecznymi nagłówkami w CLI, gwarantując niezawodne działanie na każdym systemie operacyjnym.

---

## Faza 5: Silnik uruchomieniowy i pomiar wydajności (Runner + Latency + Tokeny)

### Obserwacje i zidentyfikowane ryzyka:
1. **Ochrona przed błędem 429 Rate Limit (asyncio.Semaphore):**
   - *Problem:* Przy braku ograniczeń współbieżności zapytania do modeli zewnętrznych natychmiast przekraczają limity RPM/TPM w CI/CD, powodując błędy sieciowe `HTTP 429`.
   - *Rozwiązanie:* `EvalRunner` wykorzystuje `asyncio.Semaphore(max_concurrency=10)`, co pozwala na zrównoleglenie ewaluacji przy zachowaniu bezpiecznego pułapu obciążenia API dostawcy.

2. **Średnia arytmetyczna vs percentyle (P50 i P95 Latency):**
   - *Wniosek:* Średnia arytmetyczna ukrywa pojedyncze powolne zapytania (tzw. tail latency). Zastosowanie percentyli `P50` (mediana) oraz `P95` (95. percentyl) w `compute_run_summary` pozwala natychmiast wykryć degradację wydajności dla zapytań złożonych (multi-hop / duże konteksty).

3. **Izolacja interfejsu RAG (RAG Protocol Flexibility):**
   - *Wniosek:* Różne frameworki RAG (LangChain, LlamaIndex, custom pipelines) zwracają obiekty o różnych polach (`answer`, `response`, `context` vs `contexts`, słowniki lub obiekty domenowe). W `EvalRunner.evaluate_single` zaimplementowano uniwersalną normalizację, co zapobiega awariom integracyjnym.

4. **Trwałość artefaktów ewaluacyjnych:**
   - *Wniosek:* Wygenerowany raport JSON zawiera zarówno podsumowanie statystyczne z commit SHA i gałęzią Git, jak i pełen wykaz pojedynczych przypadków testowych (`cases`), co stanowi kompletne wejście dla komparatora A/B w Fazie 6.

---

## Faza 6: Moduł porównawczy A/B i detektor regresji (Baseline vs Candidate)

### Obserwacje i zidentyfikowane ryzyka:
1. **Zjawisko cichej regresji (Silent Regression Trap):**
   - *Problem:* Zmiana w promptcie bazowym może podnieść ogólną średnią wierność (np. +3%), ale zepsuć 2 kluczowe zapytania o krytycznym znaczeniu biznesowym (spadek 1.0 -> 0.0). Zwykłe porównanie średnich globalnych nie zauważy takiego incydentu.
   - *Rozwiązanie:* `compare_runs` w `src/judgekit/comparator.py` prowadzi analizę na dwóch poziomach: **Global Delta** ($\Delta_{\text{metric}}$) oraz **Pointwise Diff** per rekord ze zliczaniem `critical_regressions_count`.

2. **Dopasowywanie przypadków testowych w A/B:**
   - *Wniosek:* Jeśli w gałęzi kandydata dodano lub usunięto przypadek testowy, komparator porównuje wyłącznie część wspólną identyfikatorów (`test_id`), odnotowując `total_compared_cases`. Zapobiega to zakłamaniom różnic wynikającym ze zmian rozmiaru próby.

3. **Determinizm kodów wyjścia (CLI Exit Codes):**
   - *Wniosek:* Aby pipeline w CI mógł jednoznacznie decydować o przejściu lub zatrzymaniu buildu, skrypt `cli_compare.py` weryfikuje twarde reguły progowe (`--max-regressions`, `--max-p95-latency-increase-ms`, `--max-faithfulness-drop`) i zwraca `sys.exit(1)` przy jakimkolwiek naruszeniu.

---

## Faza 7: Integracja bramki CI/CD (GitHub Actions Quality Gate)

### Obserwacje i zidentyfikowane ryzyka:
1. **Zimny start repozytorium (Cold Start Baseline):**
   - *Problem:* Podczas pierwszego uruchomienia workflow na nowym repozytorium artefakt `baseline-eval-result` nie istnieje jeszcze w magazynie GitHub Actions (`actions/download-artifact` zakończyłby się błędem).
   - *Rozwiązanie:* W `.github/workflows/eval_gate.yml` dodano `continue-on-error: true` przy pobieraniu artefaktu oraz krok rezerwowy generujący lokalny baseline, jeśli plik nie został pobrany z chmury.

2. **Dwuetapowy cykl życia artefaktów (PR vs Main):**
   - *Wniosek:* Rozdzielenie workflow na dwa procesy:
     - `eval_gate.yml` (uruchamiany na `pull_request` – ewaluacja kandydata, komparacja, blokada PR kodem `sys.exit(1)`),
     - `update_baseline.yml` (uruchamiany po `push` do `main` – publikacja zaktualizowanego oficjalnego baseline).
     Zapewnia to, że deweloperzy w PR zawsze porównują się ze stabilnym stanem produkcyjnym bez ryzyka wyścigu baseline'ów.

3. **Separacja sekretów i testów jednostkowych:**
   - *Wniosek:* Krok `pytest tests/unit/` w GitHub Actions wykonuje się przed odpytaniem sędziów AI, co natychmiast blokuje PR w przypadku błędów syntaktycznych lub logicznych bez ponoszenia kosztów tokenów API.

---

## Faza 8: Raportowanie PR (Bot komentujący w Markdown)

### Obserwacje i zidentyfikowane ryzyka:
1. **Unikanie spamu w konwersacji Pull Requesta (Idempotentne komentarze):**
   - *Problem:* Jeśli bot publikuje nowy komentarz przy każdym commit pushniętym do brancha PR, konwersacja pod PR-em szybko staje się nieczytelna.
   - *Rozwiązanie:* Zaimplementowano znacznik HTML `<!-- judgekit-pr-comment -->` w nagłówku generowanego Markdownu. `pr_commenter.py` przeszukuje istniejące komentarze pod danym PR-em i jeśli znajdzie komentarz z tym tagiem, aktualizuje go metodą `PATCH /repos/{repo}/issues/comments/{comment_id}` zamiast tworzyć kolejny (`POST`).

2. **Bezpieczeństwo uprawnień w GitHub Actions (`permissions: pull-requests: write`):**
   - *Problem:* Domyślne uprawnienia `GITHUB_TOKEN` w nowo zakładanych repozytoriach GitHub często mają tryb `read-only`, co powodowałoby błąd HTTP 403 przy próbie zapisu komentarza.
   - *Rozwiązanie:* Do workflow `eval_gate.yml` dodano sekcję `permissions` jawnie przyznającą uprawnienia `pull-requests: write` oraz `issues: write`.

3. **Kodowanie terminala Windows (cp1250 / Unicode):**
   - *Problem:* Narzędzie CLI `cli_comment.py` wypisujące raport Markdown zawierający emoji (`✅`, `❌`, `⚖️`) rzucało wyjątek `UnicodeEncodeError: 'charmap'` w domyślnej powłoce Windows PowerShell.
   - *Rozwiązanie:* Wprowadzono automatyczną rekonfigurację strumieni `sys.stdout` i `sys.stderr` do kodowania `utf-8` z obsługą `errors="replace"`.

4. **Widoczność diagnostyczna (Chain-of-Thought w `<details>`):**
   - *Wniosek:* Zgrupowanie wykrytych regresji w zwijany blok HTML `<details>` pozwala inżynierom natychmiast zobaczyć ogólny stan w tabeli podsumowującej, a w razie potrzeby jednym kliknięciem sprawdzić pełne uzasadnienie LLM (CoT) dla każdego zepsutego przypadku testowego.

---

## Faza 9: Dashboard trendów i historii (Streamlit + SQLite)

### Obserwacje i zidentyfikowane ryzyka:
1. **Separacja danych operacyjnych od repozytorium kodu (`.gitignore`):**
   - *Problem:* Pliki bazy danych SQLite (`data/*.db`) oraz surowe zrzuty ewaluacji nie powinny być commitowane do repozytorium Git, by uniknąć konfliktów binarnych przy równoległych wdrożeniach.
   - *Rozwiązanie:* Plik `data/eval_history.db` jest ignorowany w `.gitignore`, natomiast w pipeline CI (`update_baseline.yml`) baza danych jest wersjonowana i archiwizowana jako artefakt GitHub Actions (`eval-history-db`).

2. **Indeksowanie i wydajność odpytywania (SQLite Query Optimization):**
   - *Problem:* Wraz ze wzrostem liczby ewaluacji tabela `test_results` może liczyć dziesiątki tysięcy rekordów, co spowalniałoby interaktywne filtrowanie w aplikacji Streamlit.
   - *Rozwiązanie:* W module `storage.py` utworzono jawne indeksy `idx_test_results_run_id` oraz `idx_runs_timestamp`, redukując czas zapytania do ułamków milisekund.

3. **Interaktywna analiza jakości i audyt CoT w UI:**
   - *Wniosek:* Zintegrowanie interaktywnego inspektora błędów z opcją filtrowania (`show_failures_only`) oraz wyszukiwarką pełnotekstową po ID i zapytaniu pozwala zespołowi AI natychmiast wyizolować halucynacje z dowolnego historycznego wdrożenia.

---

## Faza 10: Podpięcie pod docelowy projekt RAG i test na wstrzykniętych regresjach (Chaos Eval)

### Obserwacje i zidentyfikowane ryzyka:
1. **Elastyczność integracji przez Adapter (`RAGSystemAdapter`):**
   - *Wniosek:* Systemy RAG w Pythonie przyjmują skrajnie różne formy wywołań (obiekty z metodą `arun()`, callable, słowniki LangChain/LlamaIndex z `source_documents`). Wprowadzenie adaptera z mechanizmem automatycznej normalizacji wyjścia do `RAGResponse` (odpowiedź, lista kontekstów tekstowych, tokeny i czas) uniezależnia `JudgeKit` od biblioteki RAG, z której korzysta zespół.

2. **Empiryczna walidacja reguł Quality Gate (Chaos Engineering):**
   - *Weryfikacja:* Przetestowano 4 powszechne scenariusze degradacji systemów RAG:
     - `chaos/bad-chunking`: Zmniejszenie rozmiaru fragmentów (512 -> 128 tokenów) rozbija fakty w zapytaniach wielokrokowych (*multi-hop*), wywołując spadek wierności $\Delta_{\text{faith}} = -0.20$ oraz 4 regresje krytyczne $\implies$ natychmiastowa blokada PR.
     - `chaos/top-k-drop`: Ograniczenie `top_k` (5 -> 1) odcina model od dowodów źródłowych, zmuszając go do zmyślania faktów ($\Delta_{\text{faith}} = -0.15$, 3 regresje krytyczne) $\implies$ natychmiastowa blokada PR.
     - `chaos/sloppy-prompt`: Usunięcie guardrailu uziemiającego (*„odpowiedz nie wiem”*) skutkuje halucynowaniem na pytaniach spoza domeny (2 regresje krytyczne $1.0 \to 0.0$) $\implies$ natychmiastowa blokada PR.
     - `chaos/heavy-reranker`: Wolny reranker zachowuje jakość, lecz drastycznie zwiększa opóźnienie (+450 ms), naruszając SLO P95 (+250 ms) $\implies$ natychmiastowa blokada PR.
   - *Wynik:* **Regression Detection Rate = 100.0%** (4/4 zablokowane szkodliwe commity).

3. **Status gotowości produkcyjnej:**
   - Wszystkie 10 faz systemu `JudgeKit` zostało wdrożonych, udokumentowanych i przetestowanych (54/54 testów jednostkowych przechodzi pomyślnie).

---
