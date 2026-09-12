# TheJudge (JudgeKit) ⚖️

> Automated continuous LLM-as-a-Judge evaluation and CI/CD quality gate for production RAG pipelines. Prevents silent regressions with calibrated pointwise scoring, Cohen's Kappa, and latency SLOs.

**JudgeKit** to produkcyjny system ciągłej ewaluacji LLM-as-a-Judge w CI/CD dedykowany aplikacjom RAG (Retrieval-Augmented Generation).

## Architektura i Założenia

System realizuje ciągłą kontrolę jakości aplikacji opartych na LLM poprzez:
1. **Rygorystyczne kontrakty danych i schematy Golden Set** (Pydantic v2).
2. **Modularnych Sędziów (LLM-as-a-Judge)** z wymuszonym Chain-of-Thought i Discrete Rubric Scoring.
3. **Kalibrację z ekspertem ludzkim (Inter-rater reliability / Cohen's Kappa > 0.80)**.
4. **Asynchroniczny runner ewaluacyjny** z kontrolą współbieżności (semaphores) oraz analizą opóźnień (P50, P95) i kosztów tokenowych.
5. **Komparator A/B i detektor regresji** (Baseline vs Candidate) zapobiegający silent regression.
6. **Bramkę jakości CI/CD (GitHub Actions Quality Gate)** blokującą niedopuszczalne regresje w PR.
7. **Bota komentującego PR** z przejrzystym raportem Markdown.
8. **Dashboard analityczny trendów historycznych** (Streamlit / SQLite).
9. **Testy odpornościowe (Chaos Eval)** weryfikujące wykrywalność awarii RAG.

## Struktura Projektu

```plaintext
TheJudge/
├── src/
│   └── judgekit/
├── tests/
│   ├── evals/
│   │   └── data/
│   └── unit/
├── documentation/
├── artifacts/
├── .gitignore
├── pyproject.toml / requirements.txt
└── README.md
```
