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
