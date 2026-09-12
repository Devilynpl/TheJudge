# Faza 9: Dashboard trendów i historii (Streamlit + SQLite)

Komentarz pod PR (Faza 8) działa jak bezpiecznik na poziomie pojedynczego commita. Z czasem pojawia się jednak potrzeba widoku strategicznego: *„Czy przez ostatnie 3 miesiące jakość sukcesywnie rośnie, czy stopniowo narasta opóźnienie (latency creep) i puchną koszty tokenów?”*.

**Cel:** stworzyć lekki, interaktywny dashboard analityczny oparty o SQLite i Streamlit, który wizualizuje trendy metryk w czasie oraz pozwala na audyt pojedynczych odpowiedzi i halucynacji.

---

### 1. Schemat relacyjnej bazy danych (`eval_history.db`)
Wszystkie oficjalne przebiegi zapisujemy w relacyjnej bazie SQLite w dwóch powiązanych tabelach:
- `runs`: podsumowanie całego testu (agregaty, wersja commita, metryki globalne P95, mean faithfulness, koszt).
- `test_results`: szczegółowy zrzut per pytanie (wygenerowana odpowiedź, punkty, uzasadnienie CoT sędziego).

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
    FOREIGN KEY(run_id) REFERENCES runs(run_id)
);
```

---

### 2. Aplikacja analityczna (`dashboard.py`)
Skrypt Streamlit pobiera historię z bazy i generuje wykresy trendów oraz interaktywny inspektor błędów:

```python
import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="JudgeKit Trends", layout="wide")
st.title("⚖️ JudgeKit: Historia Jakości i Wydajności")

# Połączenie z bazą
conn = sqlite3.connect("data/eval_history.db")

# 1. Pobranie danych zagregowanych
runs_df = pd.read_sql_query(
    """
    SELECT run_id, timestamp, commit_sha, branch, 
           mean_faithfulness, mean_relevance, p95_latency_ms, total_cost_usd 
    FROM runs 
    ORDER BY timestamp ASC
    """,
    conn
)

if runs_df.empty:
    st.info("Brak zarejestrowanych przebiegów. Uruchom ewaluację, aby zasilić bazę.")
    st.stop()

# 2. Wykresy trendów jakości i opóźnień
col1, col2 = st.columns(2)

with col1:
    st.subheader("Wierność i Trafność w czasie")
    fig_quality = px.line(
        runs_df, 
        x="timestamp", 
        y=["mean_faithfulness", "mean_relevance"],
        markers=True,
        labels={"value": "Wynik (0.0 - 1.0)", "timestamp": "Data wdrożenia"}
    )
    st.plotly_chart(fig_quality, use_container_width=True)

with col2:
    st.subheader("P95 Latency (ms)")
    fig_latency = px.line(
        runs_df, 
        x="timestamp", 
        y="p95_latency_ms",
        markers=True,
        labels={"p95_latency_ms": "Opóźnienie P95 [ms]", "timestamp": "Data wdrożenia"}
    )
    st.plotly_chart(fig_latency, use_container_width=True)

# 3. Inspektor błędów (Deep Dive w konkretny commit)
st.divider()
st.subheader("🔍 Inspektor pojedynczych odpowiedzi i halucynacji")

selected_run = st.selectbox(
    "Wybierz przebieg do analizy:", 
    runs_df["run_id"].iloc[::-1],
    format_func=lambda x: f"Run: {x[:8]} | Commit: {runs_df.loc[runs_df['run_id']==x, 'commit_sha'].values[0][:7]}"
)

results_df = pd.read_sql_query(
    """
    SELECT test_id, query, generated_answer, faithfulness_score, faithfulness_reasoning 
    FROM test_results 
    WHERE run_id = ?
    """,
    conn,
    params=(selected_run,)
)

show_failures_only = st.checkbox("Pokaż tylko błędy (Faithfulness < 1.0)", value=True)
if show_failures_only:
    results_df = results_df[results_df["faithfulness_score"] < 1.0]

st.dataframe(results_df, use_container_width=True)
```

---

### 3. Ingest danych po scaleniu (`ingest_run.py`)
Kiedy PR zostaje scalony do `main`, skrypt ingestu pobiera plik `eval_run_<commit_sha>.json` i dopisuje rekord do bazy SQLite, zasilając historyczne wykresy.