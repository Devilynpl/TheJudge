# Faza 8: Raportowanie PR (Bot komentujący w Markdown)

Samo zablokowanie pipeline'u w CI to za mało — programista nie powinien przekopywać się przez tysiące linii surowych logów w zakładce GitHub Actions, żeby dowiedzieć się, dlaczego build jest czerwony. Informacja zwrotna musi pojawić się natychmiast w miejscu pracy: **wprost jako czytelny komentarz bota pod Pull Requestem**.

**Cel:** wygenerować przejrzysty raport porównawczy w formacie Markdown i automatycznie wstawiać go lub aktualizować pod otwartym PR-em po każdym pushu.

---

### 1. Struktura idealnego komentarza PR
Raport musi umożliwiać diagnozę problemu w 5 sekund:

- [x] ~~**Status Badge:** Czytelny status: zielony (`EVAL PASSED`) lub czerwony (`EVAL BLOCKED`).~~
- [x] ~~**Kompaktowa tabela metryk:** Wartości z `main`, wartości z PR oraz różnica $\Delta$.~~
- [x] ~~**Rozwijana sekcja regresji (`<details>`):** Precyzyjne wskazanie, które konkretnie zapytania z Golden Setu uległy pogorszeniu wraz z uzasadnieniem sędziego (Chain-of-Thought).~~

#### Przykładowy format raportu Markdown:

```markdown
## ⚖️ JudgeKit Evaluation Report

| Status | Metric | Baseline (`main`) | Candidate (PR) | Delta | Threshold |
| :---: | :--- | :---: | :---: | :---: | :---: |
| ✅ | **Faithfulness** | 0.8500 | 0.8750 | **+0.0250** | $\ge -0.02$ |
| ✅ | **Relevance** | 0.9000 | 0.9000 | **0.0000** | $\ge -0.05$ |
| ❌ | **P95 Latency** | 320 ms | 610 ms | **+290 ms** | $\le +250\text{ ms}$ |
| ❌ | **Critical Regressions** | 0 | 1 | **+1** | **0** |

<details>
<summary><b>🔍 Zidentyfikowane regresje jakościowe (1 przypadek)</b></summary>

- **Case ID:** `eval-015`
  - **Spadek noty:** z `1.0` do `0.0`
  - **Uzasadnienie sędziego:** Model skrócił odpowiedź i pominął kluczowy warunek gwarancji na akumulator, wprowadzając użytkownika w błąd.
</details>
```

---

### 2. Generator komentarza (`pr_commenter.py`)
- [x] ~~Skrypt generuje powyższy raport na podstawie pliku `diff_report.json` i przy użyciu tokenu GitHub (`GITHUB_TOKEN`) dodaje lub edytuje komentarz pod danym numerem Pull Requesta.~~
- [x] ~~Wdrożenie modułu CLI `judgekit.cli_comment` oraz integracja kroków w GitHub Actions workflow (`eval_gate.yml`).~~