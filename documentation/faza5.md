# ~~Faza 5: Silnik uruchomieniowy i pomiar wydajności (Runner + Latency + Tokeny)~~ [ZREALIZOWANE]

- [x] ~~Ewaluacja 60 zapytań sekwencyjnie w pętli `for` trwa zbyt długo. Żaden inżynier ani pipeline CI nie zaakceptuje tak długiego czasu oczekiwania na Pull Request.~~
- [x] ~~**Cel:** zbudować asynchroniczny silnik testowy (`EvalRunner`), który wykona całą ewaluację w 15–25 sekund, rejestrując jednocześnie kluczowe metryki operacyjne (opóźnienie, zużycie tokenów, estymowany koszt).~~

---

### ~~1. Architektura równoległego Runnera (Asyncio + Semafory)~~
- [x] ~~API modeli komercyjnych (OpenAI, Anthropic) nakłada limity zapytań na minutę (RPM/TPM). Niekontrolowane `asyncio.gather()` bez ograniczeń doprowadzi do błędu `429 Rate Limit Exceeded`.~~
- [x] ~~Używamy semafora (`asyncio.Semaphore`), aby kontrolować liczbę współbieżnych zapytań (np. domyślnie max 10 równolegle).~~
- [x] ~~Cykl wykonania pojedynczego przypadku:~~
  - [x] ~~1. Pomiar czasu startu (`time.perf_counter()`).~~
  - [x] ~~2. Asynchroniczne wywołanie testowanego systemu RAG (wyszukanie kontekstów + generacja odpowiedzi).~~
  - [x] ~~3. Rejestracja `latency_ms` oraz liczby tokenów wejściowych i wyjściowych.~~
  - [x] ~~4. Równoległe przekazanie wygenerowanego wyniku do sędziów (Faithfulness, Relevance, Safety).~~
  - [x] ~~5. Zagregowanie wyników do zunifikowanego obiektu `PipelineMetrics`.~~

---

### ~~2. Kod rdzenia silnika (`runner.py`)~~
- [x] ~~Zaimplementowano klasę `EvalRunner` w module `src/judgekit/runner.py` oraz narzędzie CLI `src/judgekit/cli_runner.py`.~~

```python
~~class EvalRunner:~~
~~    def __init__(self, rag_client, judge_client, max_concurrency: int = 10):~~
~~        self.rag = rag_client~~
~~        self.judge = judge_client~~
~~        self.semaphore = asyncio.Semaphore(max_concurrency)~~
```

---

### ~~3. Agregacja statystyczna: Dlaczego średnia arytmetyczna kłamie?~~
- [x] ~~Dla wierności i trafności średnia jest przydatna, lecz dla metryk operacyjnych (czas i tokeny) średnia maskuje drastyczne anomalie wydajnościowe.~~
- [x] ~~Silnik wylicza percentyle i rozkłady statystyczne:~~
  - [x] ~~**P50 Latency:** Typowy czas odpowiedzi użytkownika (mediana).~~
  - [x] ~~**P95 Latency:** Czas dla 5% najwolniejszych zapytań (np. trudne zapytania multi-hop lub zbyt duże chunki).~~
  - [x] ~~**Avg Faithfulness:** Średni wskaźnik ugruntowania faktograficznego.~~
  - [x] ~~**Failure Count (`score == 0.0`):** Liczba krytycznych błędów biznesowych i halucynacji.~~

---

### ~~4. Wynik fazy: Trwały zrzut ewaluacji (`eval_run_<sha>.json`)~~
- [x] ~~Każde uruchomienie runnera generuje w katalogu `artifacts/` plik JSON oznaczony hashem commita lub identyfikatorem buildu (`eval_run_<commit_sha>.json` / `baseline.json` / `candidate.json`). Będzie on fundamentem porównań A/B w kolejnych etapach.~~