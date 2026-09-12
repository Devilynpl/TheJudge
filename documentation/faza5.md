# Faza 5: Silnik uruchomieniowy i pomiar wydajności (Runner + Latency + Tokeny)

Ewaluacja 60 zapytań sekwencyjnie w pętli `for` trwa zbyt długo: 60 zapytań do RAG $\times$ 2 sekundy + 60 ocen sędziego $\times$ 1.5 sekundy daje niemal 4 minuty. Żaden inżynier ani pipeline CI nie zaakceptuje tak długiego czasu oczekiwania na Pull Request.

**Cel:** zbudować asynchroniczny silnik testowy (`EvalRunner`), który wykona całą ewaluację w 15–25 sekund, rejestrując jednocześnie kluczowe metryki operacyjne (opóźnienie, zużycie tokenów, estymowany koszt).

---

### 1. Architektura równoległego Runnera (Asyncio + Semafory)
API modeli komercyjnych (OpenAI, Anthropic) nakłada limity zapytań na minutę (RPM/TPM). Niekontrolowane `asyncio.gather()` bez ograniczeń doprowadzi do błędu `429 Rate Limit Exceeded`.

Używamy semafora (`asyncio.Semaphore`), aby kontrolować liczbę współbieżnych zapytań (np. domyślnie max 10 równolegle).

#### Cykl wykonania pojedynczego przypadku:
1. Pomiar czasu startu (`time.perf_counter()`).
2. Asynchroniczne wywołanie testowanego systemu RAG (wyszukanie kontekstów + generacja odpowiedzi).
3. Rejestracja `latency_ms` oraz liczby tokenów wejściowych i wyjściowych.
4. Równoległe przekazanie wygenerowanego wyniku do sędziów (Faithfulness, Relevance, Safety).
5. Zagregowanie wyników do zunifikowanego obiektu `PipelineMetrics`.

---

### 2. Kod rdzenia silnika (`runner.py`)

```python
import asyncio
import time
from typing import List
from pydantic import BaseModel
import httpx

class PipelineMetrics(BaseModel):
    test_id: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    faithfulness_score: float
    relevance_score: float

class EvalRunner:
    def __init__(self, rag_client, judge_client, max_concurrency: int = 10):
        self.rag = rag_client
        self.judge = judge_client
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def _evaluate_single(self, test_case: dict) -> PipelineMetrics:
        async with self.semaphore:
            t0 = time.perf_counter()
            
            # 1. Wywołanie testowanego systemu RAG
            rag_result = await self.rag.aquery(test_case["query"])
            latency_ms = (time.perf_counter() - t0) * 1000.0

            # 2. Równoległe wywołanie sędziów
            faith_task = self.judge.a_eval_faithfulness(
                context=rag_result.context, answer=rag_result.answer
            )
            rel_task = self.judge.a_eval_relevance(
                query=test_case["query"], answer=rag_result.answer
            )
            faith_res, rel_res = await asyncio.gather(faith_task, rel_task)

            # 3. Wyliczenie kosztu (stawki za 1M tokenów)
            cost = (rag_result.input_tokens * 0.15 + rag_result.output_tokens * 0.60) / 1_000_000

            return PipelineMetrics(
                test_id=test_case["id"],
                latency_ms=round(latency_ms, 2),
                input_tokens=rag_result.input_tokens,
                output_tokens=rag_result.output_tokens,
                cost_usd=round(cost, 6),
                faithfulness_score=faith_res.score,
                relevance_score=rel_res.score,
            )

    async def run_suite(self, test_cases: List[dict]) -> List[PipelineMetrics]:
        tasks = [self._evaluate_single(tc) for tc in test_cases]
        return await asyncio.gather(*tasks)
```

---

### 3. Agregacja statystyczna: Dlaczego średnia arytmetyczna kłamie?
Dla wierności i trafności średnia jest przydatna, lecz dla metryk operacyjnych (czas i tokeny) średnia maskuje drastyczne anomalie wydajnościowe. Silnik musi wyliczać percentyle:

- **P50 Latency:** Typowy czas odpowiedzi użytkownika (mediana).
- **P95 Latency:** Czas dla 5% najwolniejszych zapytań (np. trudne zapytania multi-hop lub zbyt duże chunki).
- **Avg Faithfulness:** Średni wskaźnik ugruntowania faktograficznego.
- **Failure Count (`score == 0.0`):** Liczba krytycznych błędów biznesowych i halucynacji.

```python
import numpy as np

def compute_run_summary(results: List[PipelineMetrics]) -> dict:
    latencies = [r.latency_ms for r in results]
    faith_scores = [r.faithfulness_score for r in results]
    
    return {
        "p50_latency_ms": float(np.percentile(latencies, 50)),
        "p95_latency_ms": float(np.percentile(latencies, 95)),
        "mean_faithfulness": float(np.mean(faith_scores)),
        "critical_failures": sum(1 for s in faith_scores if s == 0.0),
        "total_cost_usd": round(sum(r.cost_usd for r in results), 6),
    }
```

---

### 4. Wynik fazy: Trwały zrzut ewaluacji (`eval_run_<sha>.json`)
Każde uruchomienie runnera generuje w katalogu `artifacts/` plik JSON oznaczony hashem commita lub identyfikatorem buildu (`eval_run_<commit_sha>.json`). Będzie on fundamentem porównań A/B w kolejnych etapach.