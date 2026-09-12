# Faza 4: Walidacja sędziego (Human-in-the-loop & Inter-rater Agreement)

Większość projektów LLM popełnia ten sam błąd: autorzy piszą prompt sędziego, puszczają go na kilku przykładach, uznają, że „wygląda sensownie” i wrzucają do CI. To błąd krytyczny. Zanim powierzysz sędziemu blokowanie Pull Requestów, musisz zmierzyć jakość i stabilność samego sędziego.

**Cel:** dowieść matematycznie, że sędzia zgadza się z oceną człowieka na poziomie min. 80–85%, używając współczynnika **Cohen’s Kappa ($\kappa$)**.

---

### 1. Protokół ślepej próby (Calibration Run)
Wybierasz losowo 30–40 przypadków z wygenerowanymi odpowiedziami systemu (mieszanka odpowiedzi idealnych, halucynacji i błędów formatowania):
1. **Człowiek (Ekspert domenowy):** Oceniasz każdą odpowiedź niezależnie w tabeli (`tests/evals/calibration_results.csv`) w znormalizowanej skali: `0.0`, `0.5`, `1.0`. Nie widzisz wcześniejszych ocen sędziego.
2. **Sędzia automatyczny:** Przetwarza dokładnie te same przypadki z wymuszoną temperaturą `0.0`.
3. Zestawiasz obie kolumny w celach kalibracyjnych i statystycznych.

---

### 2. Matematyka zaufania: Dlaczego nie wystarczy zwykły procent zgodności?
Jeśli 90% odpowiedzi w Twoim systemie jest poprawnych, sędzia, który zawsze daje `1.0`, uzyska 90% dokładności (*accuracy*), będąc jednocześnie w 100% bezużytecznym (nie wykryje żadnego błędu).

Dlatego standardem inżynierskim w MLOps jest **Cohen’s Kappa ($\kappa$)** — metryka mierząca zgodność ponad czysty przypadek:

$$\kappa = \frac{P_o - P_e}{1 - P_e}$$

- $P_o$ (*observed agreement*): rzeczywisty odsetek zgodnych ocen.
- $P_e$ (*expected agreement*): prawdopodobieństwo, że oceniający zgodzili się przez czysty przypadek.

| Wartość $\kappa$ | Interpretacja w LLM-Ops | Działanie inżynierskie |
| :--- | :--- | :--- |
| **< 0.40** | Słaba / losowa | Sędzia bezużyteczny. Zmień model sędziego lub dopracuj rubrykę. |
| **0.41 – 0.60** | Umiarkowana | Za dużo niejednoznaczności w prompcie sędziego. |
| **0.61 – 0.80** | Dobra (Akceptowalna) | Znośny próg wejścia do CI jako ostrzeżenie (*warning*). |
| **> 0.80** | Bardzo wysoka (Złoty standard) | Sędzia gotowy do blokowania merge'a (*hard blocker*). |

---

### 3. Skrypt walidacyjny w Pythonie (`eval_judge_alignment.py`)
Do wyliczenia współczynnika i macierzy pomyłek używamy `scikit-learn` oraz `pandas`:

```python
import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

# Dane z pliku kalibracyjnego (kolumny: test_id, human_score, judge_score, judge_reasoning)
df = pd.read_csv("tests/evals/calibration_results.csv")

human = df["human_score"].astype(str)
judge = df["judge_score"].astype(str)

# Wyliczenie metryki Cohena
kappa = cohen_kappa_score(human, judge)
print(f"Cohen's Kappa: {kappa:.3f}")

# Macierz pomyłek - pokazuje, gdzie sędzia ma tendencję do mylenia się
labels = ["0.0", "0.5", "1.0"]
cm = confusion_matrix(human, judge, labels=labels)
cm_df = pd.DataFrame(cm, index=[f"Human {l}" for l in labels], columns=[f"Judge {l}" for l in labels])
print("\nMacierz pomyłek:")
print(cm_df)
```

---

### 4. Pętla doskonalenia sędziego (Error Analysis & Few-shot Injection)
Podczas przeglądu macierzy pomyłek szukamy dwóch konkretnych anomalii:

1. **False Positive (Groźne):** Człowiek ocenił na `0.0` (halucynacja), a sędzia przyznał `1.0`.
   - *Przyczyna:* Model sędziowski użył własnej wiedzy pre-treningowej zamiast opierać się wyłącznie na dostarczonym kontekście.
   - *Poprawka:* Dodaj do promptu sędziego explicite zasadę: *„Nawet jeśli twierdzenie jest prawdą w Wikipedii, brak tego faktu w sekcji KONTEKST oznacza ocenę 0.0”*.
2. **False Negative (Frustrujące):** Człowiek ocenił na `1.0` (poprawna parafraza), a sędzia wystawił `0.0`.
   - *Przyczyna:* Sędzia wymagał dosłownych słów kluczowych.
   - *Poprawka:* Wstrzyknij przykłady typu Few-Shot bezpośrednio do promptu sędziego, demonstrujące dopuszczalną synonimię.