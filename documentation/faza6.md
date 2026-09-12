Faza 6: Moduł porównawczy A/B i detektor regresji (Baseline vs Candidate)Samo uruchomienie testu i wyświetlenie np. „Faithfulness: 84%” nie odpowiada na kluczowe pytanie inżyniera: „Czy ta zmiana w kodzie poprawiła system, czy coś popsuła?”.Jeśli średnia metryka wzrośnie z 80% na 82%, na pozór jest lepiej. Jednak w środku model mógł poprawić 4 proste pytania, ale kompletnie wywalić się na 2 kluczowych zapytaniach biznesowych. Taki scenariusz to cicha regresja (silent regression).Cel: zbudować moduł porównujący dwa przebiegi (Baseline / gałąź główna vs Candidate / gałąź z Pull Requesta) na poziomie globalnym oraz per-case.1. Matematyka regresji: Global Delta vs Pointwise RegressionsModuł A/B musi wyliczać dwa poziomy różnic:Global Delta ($\Delta$): Różnica zagregowanych wskaźników:$$\Delta_{\text{metric}} = \text{Metric}_{\text{candidate}} - \text{Metric}_{\text{baseline}}$$Net Regression Rate (Czysty bilans zmian):Wzrosty (Improvements): zapytania, gdzie ocena wzrosła (np. $0.0 \to 1.0$).Regresje (Regressions): zapytania, gdzie ocena spadła (np. $1.0 \to 0.0$ lub $1.0 \to 0.5$).Nawet przy $\Delta > 0$, pojedyncza regresja krytyczna (drop o $\ge 0.5$) powinna być wyraźnie oflagowana.2. Implementacja komparatora (comparator.py)Komparator wczytuje dwa zrzuty JSON z Fazy 5 (baseline.json i candidate.json) i wypluwa precyzyjny bilans:Pythonfrom pydantic import BaseModel
from typing import List, Dict

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
        baseline_commit=baseline_data["commit_sha"],
        candidate_commit=candidate_data["commit_sha"],
        delta_faithfulness=round(delta_faith, 4),
        delta_relevance=round(delta_rel, 4),
        delta_p95_latency_ms=round(delta_p95, 2),
        regressions=regressions,
        improvements=improvements
    )
3. Skąd wziąć plik Baseline w realnym projekcie?Najczęstszy problem techniczny: „Przeciwko czemu porównujemy kod w gałęzi feature/new-prompt?”.Stosuje się dwie strategie:Dynamic Baseline (W locie w CI): GitHub Action pobiera kod z main, uruchamia runnera, potem przełącza się na gałąź PR i uruchamia go drugi raz.Wada: Podwaja czas i koszt wykonania testu.Artifact Baseline (Zalecana w LLM-Ops): Przy każdym merge'u do gałęzi main, CI zapisuje plik baseline_eval.json jako trwały artefakt (np. w GitHub Actions Artifacts, AWS S3 lub bazie danych). W gałęzi PR runner uruchamia się tylko raz dla nowego kodu i pobiera ostatni oficjalny artefakt z main do porównania.4. Wynik fazy: Wyjście z kodem błędu (CLI Exit Code)Komparator udostępnia prosty interfejs wiersza poleceń (CLI). To on będzie decydować, czy pipeline w CI ma przejść, czy zakończyć się kodem błędu (sys.exit(1)):Bashpython -m judgekit.compare \
  --baseline artifacts/baseline.json \
  --candidate artifacts/candidate.json \
  --max-regressions 0 \
  --max-p95-latency-increase-ms 200
Jeśli wykryto choć 1 krytyczną regresję lub opóźnienie skoczyło powyżej limitu — proces zwraca kod błędu i generuje plik podsumowujący.