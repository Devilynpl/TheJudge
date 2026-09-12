# ~~Faza 2: Budowa Golden Setu i Versioning-as-Code~~ [ZREALIZOWANE]

### ~~2. Trzy metody pozyskiwania próbek (Syntetyczne + Realistyczne)~~
- [x] ~~Nie pisz wszystkich 60 pytań ręcznie od zera — to nieefektywne:~~
  - [x] ~~**Podejście A: Logi produkcyjne / analityka (najwyższa wartość)** - autentyczne, zanonimizowane pytania użytkowników.~~
  - [x] ~~**Podejście B: Odwrócona generacja syntetyczna (LLM-assisted)** - generowanie z chunków pytań z odpowiedzią oraz pytań podchwytliwych.~~
  - [x] ~~**Podejście C: Ręczne dopracowanie złośliwych brzegów (Adversarial Crafting)** - pytania z regression cemetery (jailbreaki, edge case'y).~~

### ~~3. Format przechowywania: plik golden_set.jsonl~~
- [x] ~~Użyj formatu JSON Lines (.jsonl) zamiast wielkiego pliku .json. Dzięki temu diffy w Git są czytelne linijka po linijce, a dodanie nowego przypadku testowego to po prostu + 1 line w Pull Requeście.~~

```json
~~{"id": "eval-001", "category": "factual", "query": "Jaki jest okres gwarancji na akumulator?", "expected_behavior": "Podaj dokładnie 24 miesiące, powołując się na sekcję 4.2 gwarancji.", "reference_answer": "Okres gwarancji na akumulator wynosi 24 miesiące.", "reference_contexts": ["Sekcja 4.2: Gwarancja na wbudowane akumulatory litowo-jonowe wynosi 24 miesiące od daty zakupu."]}~~
~~{"id": "eval-002", "category": "unanswerable", "query": "Czy serwis oferuje darmowy odbiór kurierem w weekendy?", "expected_behavior": "Model musi poinformować o braku informacji w dokumentacji i odmówić zmyślania.", "reference_answer": "Dokumentacja nie zawiera informacji o darmowym odbiorze w weekendy.", "reference_contexts": []}~~
```

### ~~4. Reguła Versioning-as-Code~~
- [x] ~~Zbiór golden_set.jsonl trzymasz w repozytorium projektu w katalogu `tests/evals/data/`.~~
- [x] ~~Każda zmiana w zbiorze testowym wymaga osobnego PR z uzasadnieniem (np. „Dodano 5 pytań testujących nowy moduł faktur”).~~
- [x] ~~W metrykach CI/CD będziesz odnotowywać wersję Golden Setu (np. v1.2 lub Git commit hash), żeby nie porównywać wyników ze zbiorów o różnej liczebności.~~