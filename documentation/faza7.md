# ~~Faza 7: Integracja bramki CI/CD (GitHub Actions Quality Gate)~~ [ZREALIZOWANE]

- [x] ~~W tej fazie łączymy Runnera (Faza 5) i Komparator (Faza 6) w nienaruszalną regułę wytwarzania kodu: **Pull Request nie może zostać scalony (merged), jeśli metryki jakości spadną poniżej założonego progu lub wystąpi niedopuszczalna regresja.**~~
- [x] ~~**Cel:** skonfigurować workflow GitHub Actions, który automatycznie pobiera oficjalny baseline, uruchamia ewaluację dla nowego kodu w PR i twardo blokuje merge w razie wykrycia problemów.~~

---

### ~~1. Logika decyzyjna bramki (Quality Gate Rules)~~
- [x] ~~Pipeline weryfikuje 3 twarde warunki (**Hard Failures**):~~
  - [x] ~~1. **Brak spadku wierności:** Średnia wierność ($\Delta_{\text{faithfulness}}$) nie może spaść o więcej niż 0.02 (2 punkty procentowe).~~
  - [x] ~~2. **Zero krytycznych regresji faktograficznych:** Liczba zapytań ze spadkiem z $1.0 \to 0.0$ musi wynosić dokładnie 0.~~
  - [x] ~~3. **Limit wydajnościowy (SLO):** $P95\text{ latency}$ nie może wzrosnąć o więcej niż 250 ms w stosunku do gałęzi `main`.~~

---

### ~~2. Skrypt CLI bramki jakości (`cli_gate.py`)~~
- [x] ~~Zaimplementowano moduł `src/judgekit/gate.py` oraz narzędzie CLI `src/judgekit/cli_gate.py` zwracające kod wyjścia `sys.exit(1)` w razie naruszenia SLO lub krytycznej regresji.~~

```python
~~def evaluate_gate(diff_report_path: str):~~
~~    if delta_faith < -0.02: sys.exit(1)~~
~~    if len(critical_regressions) > 0: sys.exit(1)~~
~~    if delta_p95 > 250.0: sys.exit(1)~~
```

---

### ~~3. Workflow GitHub Actions (`.github/workflows/eval_gate.yml`)~~
- [x] ~~Utworzono workflow `.github/workflows/eval_gate.yml` uruchamiany na każdym Pull Requeście (checkout, setup python, pytest, pobranie baseline, eval kandydata, komparator A/B, twarda bramka jakości, upload artefaktów).~~

---

### ~~4. Utrzymanie aktualnego Baseline (`update_baseline.yml`)~~
- [x] ~~Utworzono workflow `.github/workflows/update_baseline.yml` aktualizujący i publikujący trwały artefakt `baseline-eval-result` po każdym merge'u do gałęzi `main`.~~