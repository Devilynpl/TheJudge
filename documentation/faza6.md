# ~~Faza 6: Moduł porównawczy A/B i detektor regresji (Baseline vs Candidate)~~ [ZREALIZOWANE]

- [x] ~~Samo uruchomienie testu i wyświetlenie np. *„Faithfulness: 84%”* nie odpowiada na kluczowe pytanie inżyniera: **„Czy ta zmiana w kodzie poprawiła system, czy coś popsuła?”**.~~
- [x] ~~**Cel:** zbudować moduł porównujący dwa przebiegi (**Baseline** z gałęzi `main` vs **Candidate** z gałęzi Pull Requesta) na poziomie globalnym oraz per-case.~~

---

### ~~1. Matematyka regresji: Global Delta vs Pointwise Regressions~~
- [x] ~~Moduł porównawczy wylicza dwa poziomy różnic:~~
  - [x] ~~**Global Delta ($\Delta$):** Różnica zagregowanych wskaźników jakości:~~
    $$\Delta_{\text{metric}} = \text{Metric}_{\text{candidate}} - \text{Metric}_{\text{baseline}}$$
  - [x] ~~**Net Regression Rate (Czysty bilans zmian pointwise):** Wzrosty (Improvements) oraz Regresje (Regressions).~~
  - [x] ~~Pojedyncza regresja krytyczna (spadek o $\ge 0.5$ lub z $1.0 \to 0.0$) jest oflagowana jako incydent jakościowy.~~

---

### ~~2. Implementacja komparatora (`comparator.py`)~~
- [x] ~~Zaimplementowano moduł `src/judgekit/comparator.py` oraz modele `CaseDiff` i `ComparisonReport`.~~

```python
~~class CaseDiff(BaseModel):~~
~~    test_id: str~~
~~    metric: str~~
~~    baseline_score: float~~
~~    candidate_score: float~~
~~    diff: float~~
~~    reason: str~~

~~class ComparisonReport(BaseModel):~~
~~    baseline_commit: str~~
~~    candidate_commit: str~~
~~    delta_faithfulness: float~~
~~    delta_relevance: float~~
~~    delta_p95_latency_ms: float~~
~~    regressions: List[CaseDiff]~~
~~    improvements: List[CaseDiff]~~
```

---

### ~~3. Skąd wziąć plik Baseline w CI/CD?~~
- [x] ~~Zaimplementowano strategię **Artifact Baseline** z generowaniem oficjalnego zrzutu `artifacts/baseline.json`.~~

---

### ~~4. Interfejs wiersza poleceń (CLI Exit Code)~~
- [x] ~~Komparator udostępnia CLI decydujący o kodzie zakończenia procesu w CI: `python -m judgekit.cli_compare` z obsługą progów `--max-regressions 0` oraz `--max-p95-latency-increase-ms 200`.~~