# Faza 6: Moduł porównawczy A/B i detektor regresji (Baseline vs Candidate)

Samo uruchomienie testu i wyświetlenie np. *„Faithfulness: 84%”* nie odpowiada na kluczowe pytanie inżyniera: **„Czy ta zmiana w kodzie poprawiła system, czy coś popsuła?”**.

Jeśli średnia metryka wzrośnie z 80% na 82%, na pozór jest lepiej. Jednak w środku model mógł poprawić 4 proste pytania, a kompletnie wywalić się na 2 kluczowych zapytaniach biznesowych. Taki scenariusz to niebezpieczna **cicha regresja** (*silent regression*).

**Cel:** zbudować moduł porównujący dwa przebiegi (**Baseline** z gałęzi `main` vs **Candidate** z gałęzi Pull Requesta) na poziomie globalnym oraz per-case.

---

### 1. Matematyka regresji: Global Delta vs Pointwise Regressions
Moduł porównawczy wylicza dwa poziomy różnic:

1. **Global Delta ($\Delta$):** Różnica zagregowanych wskaźników jakości:
   $$\Delta_{\text{metric}} = \text{Metric}_{\text{candidate}} - \text{Metric}_{\text{baseline}}$$

2. **Net Regression Rate (Czysty bilans zmian pointwise):**
   - **Wzrosty (Improvements):** zapytania, gdzie ocena wzrosła (np. $0.0 \to 1.0$).
   - **Regresje (Regressions):** zapytania, gdzie ocena spadła (np. $1.0 \to 0.0$ lub $1.0 \to 0.5$).

> Nawet przy dodatniej delcie globalnej ($\Delta > 0$), pojedyncza regresja krytyczna (spadek o $\ge 0.5$) musi być oflagowana jako potencjalny incydent jakościowy.

---

### 2. Implementacja komparatora (`comparator.py`)
Komparator wczytuje dwa zrzuty JSON (`baseline.json` i `candidate.json`) i generuje precyzyjny bilans diffów:

```python
from typing import List, Dict
from pydantic import BaseModel

class CaseDiff(BaseModel):
    test_id: str
    metric: str
    baseline_score: float
    candidate_score: float
    diff: float
    reason: str  # dlaczego kandydat dostał mniej/więcej

class ComparisonReport(BaseModel):
    baseline_commit: str
    candidate_commit: str
    delta_faithfulness: float
    delta_relevance: float
    delta_p95_latency_ms: float
    regressions: List[CaseDiff]
    improvements: List[CaseDiff]

def compare_runs(baseline_data: dict, candidate_data: dict) -> ComparisonReport:
    b_cases = {c["test_id"]: c for c in baseline_data["cases"]}
    c_cases = {c["test_id"]: c for c in candidate_data["cases"]}

    regressions = []
    improvements = []

    for test_id, c_case in c_cases.items():
        if test_id not in b_cases:
            continue
        
        b_case = b_cases[test_id]
        diff_faith = c_case["faithfulness_score"] - b_case["faithfulness_score"]
        
        if diff_faith < 0:
            regressions.append(CaseDiff(
                test_id=test_id,
                metric="faithfulness",
                baseline_score=b_case["faithfulness_score"],
                candidate_score=c_case["faithfulness_score"],
                diff=round(diff_faith, 2),
                reason=c_case.get("faithfulness_reasoning", "Brak uzasadnienia")
            ))
        elif diff_faith > 0:
            improvements.append(CaseDiff(
                test_id=test_id,
                metric="faithfulness",
                baseline_score=b_case["faithfulness_score"],
                candidate_score=c_case["faithfulness_score"],
                diff=round(diff_faith, 2),
                reason=c_case.get("faithfulness_reasoning", "")
            ))

    delta_faith = candidate_data["mean_faithfulness"] - baseline_data["mean_faithfulness"]
    delta_rel = candidate_data["mean_relevance"] - baseline_data["mean_relevance"]
    delta_p95 = candidate_data["p95_latency_ms"] - baseline_data["p95_latency_ms"]

    return ComparisonReport(
        baseline_commit=baseline_data.get("commit_sha", "unknown"),
        candidate_commit=candidate_data.get("commit_sha", "unknown"),
        delta_faithfulness=round(delta_faith, 4),
        delta_relevance=round(delta_rel, 4),
        delta_p95_latency_ms=round(delta_p95, 2),
        regressions=regressions,
        improvements=improvements
    )
```

---

### 3. Skąd wziąć plik Baseline w CI/CD?
Stosuje się dwie strategie:
- **Dynamic Baseline (w locie):** GitHub Action pobiera `main`, uruchamia test, przełącza na gałąź PR i uruchamia powtórnie. *Wada:* Podwaja czas i koszt testów.
- **Artifact Baseline (Zalecana w LLM-Ops):** Przy każdym merge'u do `main`, workflow publikuje oficjalny plik `baseline.json` jako trwały artefakt. W gałęzi PR runner uruchamia się tylko raz i pobiera ostatni stabilny artefakt.

---

### 4. Interfejs wiersza poleceń (CLI Exit Code)
Komparator udostępnia CLI decydujący o kodzie zakończenia procesu w CI:

```bash
python -m judgekit.compare \
  --baseline artifacts/baseline.json \
  --candidate artifacts/candidate.json \
  --max-regressions 0 \
  --max-p95-latency-increase-ms 200
```
Jeśli wykryto choć 1 krytyczną regresję lub opóźnienie wzrosło ponad limit, proces zwraca kod błędu (`sys.exit(1)`).