# Faza 9: Dashboard trendów i historii (Streamlit + SQLite)

Komentarz pod PR (Faza 8) działa jak bezpiecznik na poziomie pojedynczego commita. Z czasem pojawia się jednak potrzeba widoku strategicznego: *„Czy przez ostatnie 3 miesiące jakość sukcesywnie rośnie, czy stopniowo narasta opóźnienie (latency creep) i puchną koszty tokenów?”*.

**Cel:** stworzyć lekki, interaktywny dashboard analityczny oparty o SQLite i Streamlit, który wizualizuje trendy metryk w czasie oraz pozwala na audyt pojedynczych odpowiedzi i halucynacji.

---

### 1. Schemat relacyjnej bazy danych (`eval_history.db`)
- [x] ~~Wszystkie oficjalne przebiegi zapisujemy w relacyjnej bazie SQLite w dwóch powiązanych tabelach: `runs` i `test_results`.~~
- [x] ~~Implementacja modułu zarządzania schematem bazy i indeksami `src/judgekit/storage.py`.~~

```sql
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    commit_sha TEXT,
    branch TEXT,
    mean_faithfulness REAL,
    mean_relevance REAL,
    p95_latency_ms REAL,
    total_cost_usd REAL,
    golden_set_version TEXT
);

CREATE TABLE IF NOT EXISTS test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    test_id TEXT,
    query TEXT,
    generated_answer TEXT,
    faithfulness_score REAL,
    faithfulness_reasoning TEXT,
    relevance_score REAL,
    relevance_reasoning TEXT,
    latency_ms REAL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id)
);
```

---

### 2. Aplikacja analityczna (`dashboard.py`)
- [x] ~~Skrypt Streamlit (`src/judgekit/dashboard.py`) pobiera historię z bazy i generuje wykresy trendów oraz interaktywny inspektor błędów.~~
- [x] ~~Wykresy Plotly: Faithfulness & Relevance w czasie, P95 Latency SLO.~~
- [x] ~~Inspektor halucynacji z filtrowaniem błędów i rozwijanym panelem uzasadnień CoT.~~

---

### 3. Ingest danych po scaleniu (`ingest_run.py`)
- [x] ~~Skrypt ingestu (`src/judgekit/ingest_run.py`) pobiera plik z raportem ewaluacji i dopisuje rekord do bazy SQLite, zasilając historyczne wykresy.~~
- [x] ~~Integracja automatycznego zapisu i publikacji bazy SQLite w GitHub Actions workflow (`update_baseline.yml`).~~