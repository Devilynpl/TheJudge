"""Interactive Streamlit dashboard for historical trends and failure inspection."""

import sqlite3
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

from judgekit.storage import DEFAULT_DB_PATH, init_db

st.set_page_config(
    page_title="JudgeKit Trends & Quality History",
    page_icon="⚖️",
    layout="wide",
)

st.title("⚖️ JudgeKit: Historia Jakości i Wydajności RAG")
st.markdown(
    "Ciągły monitoring wierności (*Faithfulness*), trafności (*Relevance*), opóźnień SLO oraz inspekcja halucynacji."
)

db_path = DEFAULT_DB_PATH
if not db_path.exists():
    init_db(db_path)

conn = sqlite3.connect(db_path)

# 1. Pobranie danych zagregowanych
try:
    runs_df = pd.read_sql_query(
        """
        SELECT run_id, timestamp, commit_sha, branch, 
               mean_faithfulness, mean_relevance, p95_latency_ms, total_cost_usd, golden_set_version
        FROM runs 
        ORDER BY timestamp ASC
        """,
        conn,
    )
except Exception as e:
    st.error(f"Błąd odczytu bazy danych: {e}")
    st.stop()

if runs_df.empty:
    st.info("ℹ️ Brak zarejestrowanych przebiegów w bazie danych. Uruchom ewaluację i zasil bazę skryptem `judgekit.ingest_run`.")
    st.stop()

# Header metrics (Latest Run)
latest_run = runs_df.iloc[-1]
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("Ostatnia Wierność (Faithfulness)", f"{latest_run['mean_faithfulness']:.4f}")
col_m2.metric("Ostatnia Trafność (Relevance)", f"{latest_run['mean_relevance']:.4f}")
col_m3.metric("Opóźnienie P95 Latency", f"{latest_run['p95_latency_ms']:.1f} ms")
col_m4.metric("Koszty sumaryczne (USD)", f"${latest_run['total_cost_usd']:.5f}")

st.divider()

# 2. Wykresy trendów jakości i opóźnień
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Wierność i Trafność w czasie")
    fig_quality = px.line(
        runs_df,
        x="timestamp",
        y=["mean_faithfulness", "mean_relevance"],
        markers=True,
        labels={"value": "Wynik (0.0 - 1.0)", "timestamp": "Data wdrożenia", "variable": "Metryka"},
        title="Trend wskaźników jakości LLM-as-a-Judge",
    )
    fig_quality.update_layout(yaxis_range=[0.0, 1.05], hovermode="x unified")
    st.plotly_chart(fig_quality, use_container_width=True)

with col2:
    st.subheader("⚡ P95 Latency SLO (ms)")
    fig_latency = px.line(
        runs_df,
        x="timestamp",
        y="p95_latency_ms",
        markers=True,
        labels={"p95_latency_ms": "Opóźnienie P95 [ms]", "timestamp": "Data wdrożenia"},
        title="Opóźnienie odpowiedzi modelu (P95)",
    )
    fig_latency.update_layout(hovermode="x unified")
    st.plotly_chart(fig_latency, use_container_width=True)

# 3. Inspektor pojedynczych odpowiedzi i halucynacji
st.divider()
st.subheader("🔍 Inspektor pojedynczych odpowiedzi i halucynacji (Deep Dive)")

selected_run = st.selectbox(
    "Wybierz przebieg do audytu:",
    runs_df["run_id"].iloc[::-1],
    format_func=lambda x: f"Run ID: {x[:12]} | Commit: {runs_df.loc[runs_df['run_id']==x, 'commit_sha'].values[0][:7]} | Data: {runs_df.loc[runs_df['run_id']==x, 'timestamp'].values[0]}",
)

results_df = pd.read_sql_query(
    """
    SELECT test_id, query, generated_answer, faithfulness_score, faithfulness_reasoning,
           relevance_score, relevance_reasoning, latency_ms 
    FROM test_results 
    WHERE run_id = ?
    ORDER BY faithfulness_score ASC, test_id ASC
    """,
    conn,
    params=(selected_run,),
)

col_filter1, col_filter2 = st.columns([1, 3])
with col_filter1:
    show_failures_only = st.checkbox("Pokaż tylko błędy (Faithfulness < 1.0)", value=False)
with col_filter2:
    search_query = st.text_input("Filtruj po Test ID lub zapytaniu:", "")

filtered_df = results_df.copy()
if show_failures_only:
    filtered_df = filtered_df[filtered_df["faithfulness_score"] < 1.0]
if search_query:
    filtered_df = filtered_df[
        filtered_df["test_id"].str.contains(search_query, case=False, na=False)
        | filtered_df["query"].str.contains(search_query, case=False, na=False)
    ]

st.dataframe(filtered_df, use_container_width=True, height=350)

# Expandable details for selected test
if not filtered_df.empty:
    with st.expander("🔬 Szczegółowe uzasadnienie sędziego (Chain-of-Thought) dla pierwszego wyniku z tabeli"):
        first_row = filtered_df.iloc[0]
        st.write(f"**Test ID:** `{first_row['test_id']}` | **Faithfulness Score:** `{first_row['faithfulness_score']}`")
        st.write(f"**Zapytanie:** {first_row['query']}")
        st.write(f"**Wygenerowana odpowiedź:** {first_row['generated_answer']}")
        st.info(f"**Uzasadnienie sędziego (CoT):** {first_row['faithfulness_reasoning']}")
