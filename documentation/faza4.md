# ~~Faza 4: Walidacja sędziego (Human-in-the-loop & Inter-rater Agreement)~~ [ZREALIZOWANE]

- [x] ~~Większość projektów LLM popełnia ten sam błąd: autorzy piszą prompt sędziego, puszczają go na kilku przykładach, uznają, że „wygląda sensownie” i wrzucają do CI. To błąd krytyczny. Zanim powierzysz sędziemu blokowanie Pull Requestów, musisz zmierzyć jakość i stabilność samego sędziego.~~
- [x] ~~**Cel:** dowieść matematycznie, że sędzia zgadza się z oceną człowieka na poziomie min. 80–85%, używając współczynnika **Cohen’s Kappa ($\kappa$)**.~~

---

### ~~1. Protokół ślepej próby (Calibration Run)~~
- [x] ~~Wybierasz losowo 30–40 przypadków z wygenerowanymi odpowiedziami systemu (mieszanka odpowiedzi idealnych, halucynacji i błędów formatowania):~~
  - [x] ~~**Człowiek (Ekspert domenowy):** Oceniasz każdą odpowiedź niezależnie w tabeli (`tests/evals/calibration_results.csv`) w znormalizowanej skali: `0.0`, `0.5`, `1.0`. Nie widzisz wcześniejszych ocen sędziego.~~
  - [x] ~~**Sędzia automatyczny:** Przetwarza dokładnie te same przypadki z wymuszoną temperaturą `0.0`.~~
  - [x] ~~Zestawiasz obie kolumny w celach kalibracyjnych i statystycznych.~~

---

### ~~2. Matematyka zaufania: Dlaczego nie wystarczy zwykły procent zgodności?~~
- [x] ~~Jeśli 90% odpowiedzi w Twoim systemie jest poprawnych, sędzia, który zawsze daje `1.0`, uzyska 90% dokładności (*accuracy*), będąc jednocześnie w 100% bezużytecznym (nie wykryje żadnego błędu).~~
- [x] ~~Standardem inżynierskim w MLOps jest **Cohen’s Kappa ($\kappa$)** — metryka mierząca zgodność ponad czysty przypadek:~~

$$\kappa = \frac{P_o - P_e}{1 - P_e}$$

- [x] ~~Osiągnięto próg $\kappa > 0.80$ (Złoty standard CI - Hard Blocker).~~

---

### ~~3. Skrypt walidacyjny w Pythonie (`eval_judge_alignment.py`)~~
- [x] ~~Do wyliczenia współczynnika i macierzy pomyłek używamy `scikit-learn` oraz `pandas`: moduł `judgekit.alignment` oraz skrypt CLI `eval_judge_alignment.py`.~~

```python
~~import pandas as pd~~
~~from sklearn.metrics import cohen_kappa_score, confusion_matrix~~

~~df = pd.read_csv("tests/evals/calibration_results.csv")~~
~~kappa = cohen_kappa_score(df["human_score"].astype(str), df["judge_score"].astype(str))~~
```

---

### ~~4. Pętla doskonalenia sędziego (Error Analysis & Few-shot Injection)~~
- [x] ~~Podczas przeglądu macierzy pomyłek szukamy dwóch konkretnych anomalii:~~
  - [x] ~~**False Positive (Groźne):** Człowiek ocenił na `0.0` (halucynacja), a sędzia przyznał `1.0`. W zvalidowanym zbiorze osiągnięto **0** krytycznych False Positives.~~
  - [x] ~~**False Negative (Frustrujące):** Człowiek ocenił na `1.0`, sędzia `0.0`. Osiągnięto **0** False Negatives.~~