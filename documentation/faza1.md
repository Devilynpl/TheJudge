# ~~Faza 1: Zdefiniowanie kontraktu danych i schematu Golden Setu~~ [ZREALIZOWANE]

- [x] ~~Zanim napiszesz jakikolwiek prompt dla sędziego, musisz ustalić rygorystyczny schemat danych wejściowych i wyjściowych. W evalach bałagan w formacie danych mści się najszybciej.~~

### ~~1. Schemat pojedynczego przypadku testowego (Input Schema)~~
- [x] ~~Pojedynczy rekord w zbiorze testowym (test_case.json lub Pydantic) powinien zawierać:~~
  - [x] ~~`id`: unikalny identyfikator (np. rag-chunk-014).~~
  - [x] ~~`category`: typ testu (factual, edge_case, unanswerable, jailbreak, multi_hop).~~
  - [x] ~~`query`: pytanie użytkownika.~~
  - [x] ~~`expected_behavior`: krótka instrukcja, jak system powinien się zachować (np. "Odmów odpowiedzi ze względu na brak danych w kontekście").~~
  - [x] ~~`reference_answer`: opcjonalna wzorcowa odpowiedź (ground truth), jeśli pytanie jest czysto faktograficzne.~~
  - [x] ~~`reference_contexts`: opcjonalne fragmenty dokumentów, które powinny zostać znalezione (do testowania samego retrievalu).~~

```python
~~from pydantic import BaseModel, Field~~
~~from typing import Optional, List~~

~~class TestCase(BaseModel):~~
~~    id: str~~
~~    category: str~~
~~    query: str~~
~~    expected_behavior: str~~
~~    reference_answer: Optional[str] = None~~
~~    reference_contexts: Optional[List[str]] = None~~
```

### ~~2. Schemat wyniku działania systemu (Run Output Schema)~~
- [x] ~~To, co zwraca Twój testowany system (np. RAG) przed przekazaniem do sędziego:~~
  - [x] ~~`test_case_id`: powiązanie z przypadkiem testowym.~~
  - [x] ~~`generated_answer`: wygenerowana odpowiedź modelu.~~
  - [x] ~~`retrieved_contexts`: lista chunków tekstu, które faktycznie trafiły do promptu.~~
  - [x] ~~`latency_ms`: czas generacji w milisekundach.~~
  - [x] ~~`tokens_input` / `tokens_output`: zużycie tokenów.~~

### ~~3. Schemat werdyktu sędziego (Judge Verdict Schema)~~
- [x] ~~Sędzia nie może zwracać tylko cyfry (np. 4/5). Musi stosować Structured Outputs (JSON Schema) i najpierw wygenerować uzasadnienie (Chain-of-Thought), a dopiero potem punktację:~~

```python
~~class MetricEvaluation(BaseModel):~~
~~    reasoning: str = Field(description="Krok po kroku wyjaśnij, czy w odpowiedzi są halucynacje lub błędy.")~~
~~    score: float = Field(ge=0.0, le=1.0, description="Ocena od 0.0 do 1.0")~~

~~class JudgeReport(BaseModel):~~
~~    test_case_id: str~~
~~    faithfulness: MetricEvaluation~~
~~    answer_relevance: MetricEvaluation~~
~~    context_relevance: Optional[MetricEvaluation] = None~~
~~    safety: MetricEvaluation~~
```

### ~~Dlaczego to jest kluczowe w Fazie 1:~~
- [x] ~~Wymuszenie pola reasoning przed score w modelu decyzyjnym podnosi trafność ocen sędziego o 15–25% (zmniejsza zjawisko losowego przyznawania ocen).~~

