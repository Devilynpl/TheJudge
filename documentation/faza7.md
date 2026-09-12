# Faza 7: Integracja bramki CI/CD (GitHub Actions Quality Gate)

W tej fazie łączymy Runnera (Faza 5) i Komparator (Faza 6) w nienaruszalną regułę wytwarzania kodu: **Pull Request nie może zostać scalony (merged), jeśli metryki jakości spadną poniżej założonego progu lub wystąpi niedopuszczalna regresja.**

**Cel:** skonfigurować workflow GitHub Actions, który automatycznie pobiera oficjalny baseline, uruchamia ewaluację dla nowego kodu w PR i twardo blokuje merge w razie wykrycia problemów.

---

### 1. Logika decyzyjna bramki (Quality Gate Rules)
Pipeline weryfikuje 3 twarde warunki (**Hard Failures**):

1. **Brak spadku wierności:** Średnia wierność ($\Delta_{\text{faithfulness}}$) nie może spaść o więcej niż 0.02 (2 punkty procentowe).
2. **Zero krytycznych regresji faktograficznych:** Liczba zapytań ze spadkiem z $1.0 \to 0.0$ musi wynosić dokładnie 0.
3. **Limit wydajnościowy (SLO):** $P95\text{ latency}$ nie może wzrosnąć o więcej niż 250 ms w stosunku do gałęzi `main`.

---

### 2. Skrypt CLI bramki jakości (`cli_gate.py`)
Skrypt przyjmuje raport porównawczy i decyduje o kodzie wyjścia procesu systemu operacyjnego:

```python
import sys
import json
from pathlib import Path

def evaluate_gate(diff_report_path: str):
    with open(diff_report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    delta_faith = data["delta_faithfulness"]
    delta_p95 = data["delta_p95_latency_ms"]
    critical_regressions = [r for r in data["regressions"] if r["diff"] <= -0.5]

    print(f"--- WYNIK BRAMKI JAKOŚCI ---")
    print(f"Delta Faithfulness: {delta_faith:+.4f}")
    print(f"Delta P95 Latency:  {delta_p95:+.2f} ms")
    print(f"Krytyczne regresje: {len(critical_regressions)}")

    failed = False

    if delta_faith < -0.02:
        print("[FAIL] Zbyt duży spadek średniej wierności (próg: -0.02)")
        failed = True

    if len(critical_regressions) > 0:
        print(f"[FAIL] Wykryto {len(critical_regressions)} krytycznych regresji pojedynczych zapytań!")
        for r in critical_regressions:
            print(f"  - Case {r['test_id']}: spadek z {r['baseline_score']} do {r['candidate_score']}. Powód: {r['reason']}")
        failed = True

    if delta_p95 > 250.0:
        print("[FAIL] Znaczący wzrost opóźnienia P95 (przekroczono +250 ms)")
        failed = True

    if failed:
        print("\n>>> BRAMKA CI ODRZUCIŁA TEN PULL REQUEST! <<<")
        sys.exit(1)
    
    print("\n>>> BRAMKA CI ZALICZONA POMYŚLNIE <<<")
    sys.exit(0)

if __name__ == "__main__":
    evaluate_gate(sys.argv[1])
```

---

### 3. Workflow GitHub Actions (`.github/workflows/eval_gate.yml`)

```yaml
name: JudgeKit Eval Quality Gate

on:
  pull_request:
    branches: [ main ]
    paths:
      - 'src/**'
      - 'prompts/**'
      - 'tests/evals/data/**'

jobs:
  run-eval:
    runs-on: ubuntu-latest
    steps:
      - name: Pobierz kod gałęzi PR
        uses: actions/checkout@v4

      - name: Skonfiguruj środowisko Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Instalacja zależności
        run: pip install -r requirements.txt

      - name: Pobierz oficjalny Baseline z gałęzi main
        uses: actions/download-artifact@v4
        with:
          name: baseline-eval-result
          path: artifacts/
        continue-on-error: true # Jeśli to pierwszy przebieg w repozytorium

      - name: Uruchom ewaluację dla kandydata z PR
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          python -m judgekit.runner \
            --golden-set tests/evals/data/golden_set.jsonl \
            --output artifacts/candidate.json

      - name: Porównaj wyniki A/B
        run: |
          python -m judgekit.comparator \
            --baseline artifacts/baseline.json \
            --candidate artifacts/candidate.json \
            --output artifacts/diff_report.json

      - name: Wykonaj weryfikację bramki jakości (Quality Gate)
        run: |
          python -m judgekit.cli_gate artifacts/diff_report.json

      - name: Zapisz artefakty tego przebiegu
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: eval-results-pr-${{ github.event.pull_request.number }}
          path: artifacts/
```

---

### 4. Utrzymanie aktualnego Baseline (`update_baseline.yml`)
Gdy PR zostanie zaakceptowany i zmergowany do `main`, uruchamia się osobny workflow publikujący wygenerowany `candidate.json` jako nowy oficjalny `baseline-eval-result`. Dzięki temu każdy kolejny deweloper automatycznie porównuje swój kod z najświeższym stabilnym stanem aplikacji.