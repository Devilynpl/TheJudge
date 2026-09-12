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
