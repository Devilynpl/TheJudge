Faza 4: Walidacja sędziego (Human-in-the-loop & Inter-rater Agreement)Większość projektów LLM popełnia ten sam grzech: piszą prompt sędziego, puszczają go na kilku przykładach, uznają, że „wygląda sensownie” i wrzucają do CI. To błąd krytyczny. Zanim powierzysz sędziemu blokowanie Pull Requestów, musisz zmierzyć jakość samego sędziego.Cel: dowieść matematycznie, że sędzia zgadza się z oceną człowieka na poziomie min. 80–85%, używając współczynnika Cohen’s Kappa.1. Protokół ślepej próby (Calibration Run)Wybierasz losowo 30–40 przypadków z wygenerowanymi odpowiedziami systemu (mieszanka odpowiedzi idealnych, halucynacji i błędów formatowania).Człowiek (Ty / Domain Expert): Oceniasz każdą odpowiedź niezależnie w prostej tabeli (np. w pliku CSV lub Google Sheets) w skali: 0.0, 0.5, 1.0. Nie widzisz ocen sędziego.Sędzia automatyczny: Przetwarza dokładnie te same przypadki z temperaturą 0.0.Zestawiasz obie kolumny obok siebie.2. Matematyka zaufania: Dlaczego nie wystarczy zwykły procent zgodności?Jeśli 90% odpowiedzi w Twoim systemie jest poprawnych, sędzia, który zawsze daje 1.0, uzyska 90% dokładności (accuracy), będąc jednocześnie w 100% bezużytecznym (nie złapie żadnego błędu).Dlatego standardem inżynierskim jest Cohen’s Kappa ($\kappa$) — metryka mierząca zgodność ponad czysty przypadek:$$\kappa = \frac{P_o - P_e}{1 - P_e}$$$P_o$ (observed agreement): rzeczywisty odsetek zgodnych ocen.$P_e$ (expected agreement): prawdopodobieństwo, że oceniający zgodzili się przez czysty przypadek.Wartość κInterpretacja w LLM-OpsDziałanie< 0.40Słaba / losowaSędzia bezużyteczny. Zmień model sędziego lub przepisz rubrykę.0.41 – 0.60UmiarkowanaZa dużo niejednoznaczności w promptcie sędziego.0.61 – 0.80Dobra (Akceptowalna)Znośny próg wejścia do CI jako ostrzeżenie (warning).> 0.80Bardzo wysoka (Złoty standard)Sędzia gotowy do blokowania merge'a (hard blocker).3. Skrypt walidacyjny w Pythonie (eval_judge_alignment.py)Do wyliczenia używamy scikit-learn:Pythonfrom sklearn.metrics import cohen_kappa_score, confusion_matrix
import pandas as pd

# Dane z pliku kalibracyjnego
# Kolumny: test_id, human_score, judge_score, judge_reasoning
df = pd.read_csv("tests/evals/calibration_results.csv")

human = df["human_score"].astype(str)
judge = df["judge_score"].astype(str)

# Wyliczenie metryki
kappa = cohen_kappa_score(human, judge)
print(f"Cohen's Kappa: {kappa:.3f}")

# Macierz pomyłek - pokazuje, gdzie sędzia ma tendencję do mylenia się
labels = ["0.0", "0.5", "1.0"]
cm = confusion_matrix(human, judge, labels=labels)
cm_df = pd.DataFrame(cm, index=[f"Human {l}" for l in labels], columns=[f"Judge {l}" for l in labels])
print("\nMacierz pomyłek:")
print(cm_df)
4. Pętla doskonalenia sędziego (Error Analysis & Few-shot Injection)Gdy przeglądasz macierz pomyłek, szukasz konkretnych anomalii:False Positive (Groźne): Człowiek dał 0.0 (halucynacja), a sędzia dał 1.0.Przyczyna: Model sędziowski użył własnej wiedzy pre-treningowej zamiast opierać się wyłącznie na dostarczonym kontekście.Poprawka: Dodaj do promptu sędziego explicite zasadę: „Nawet jeśli twierdzenie jest prawdą w Wikipedii, brak tego faktu w sekcji KONTEKST oznacza ocenę 0.0”.False Negative (Frustrujące): Człowiek dał 1.0 (parafraza), a sędzia dał 0.0.Przyczyna: Sędzia wymagał dosłownych słów kluczowych.Poprawka: Wstrzyknij 2 przykłady typu Few-Shot bezpośrednio do promptu sędziego, demonstrujące poprawną synonimię.