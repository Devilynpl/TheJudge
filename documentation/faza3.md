# ~~Faza 3: Implementacja i kalibracja Sędziego (LLM-as-a-Judge)~~ [ZREALIZOWANE]

- [x] ~~Sędzia to serce systemu. Jeśli sędzia jest niestabilny, cały proces CI/CD traci sens, bo deweloperzy przestaną ufać wynikom.~~
- [x] ~~Cel: zaimplementować wyspecjalizowane prompty sędziowskie, wymusić determinizm strukturalny i wyeliminować typowe błędy poznawcze modeli (LLM biases).~~

### ~~1. Złote zasady projektowania promptu sędziego~~
- [x] ~~Większość implementacji LLM-as-a-Judge zawodzi przez 4 typowe zjawiska:~~
  - [x] ~~**Position Bias:** model faworyzuje pierwszą z prezentowanych opcji (w testach A/B).~~
  - [x] ~~**Verbosity Bias:** model wyżej ocenia odpowiedzi długie i kwieciste, nawet jeśli zawierają błędy.~~
  - [x] ~~**Self-Enhancement Bias:** model GPT woli odpowiedzi wygenerowane przez GPT, a Claude przez Claude'a.~~
  - [x] ~~**Score Compression:** model unika ocen skrajnych i daje wszystkim 3/5 lub 4/5.~~
- [x] ~~Rozwiązanie inżynierskie:~~
  - [x] ~~Ocenianie bezwzględne (ang. pointwise scoring) na znormalizowanych rubrykach zamiast nieprecyzyjnych skali gwiazdkowych.~~
  - [x] ~~Narzucenie skali binarnej (0 lub 1) lub wąskiej skali dyskretnej (0.0, 0.5, 1.0), popartej definicją dla każdego progu.~~
  - [x] ~~Chain-of-Thought (CoT) przed werdyktem: model najpierw wypisuje fakty, potem sprawdza sprzeczności, a na końcu decyduje o nocie.~~

### ~~2. Trzy niezależne prompty sędziowskie (Modular Judges)~~
- [x] ~~Nie wrzucaj wszystkiego do jednego promptu. Jeden sędzia = jedna odpowiedzialność.~~
  - [x] ~~**A. Sędzia Wierności (Faithfulness / Hallucination Judge):** Sprawdza wyłącznie: Czy każde twierdzenie w odpowiedzi wynika bezpośrednio z dostarczonego kontekstu?~~
  - [x] ~~**B. Sędzia Trafności (Answer Relevance Judge):** Sprawdza wyłącznie: Czy odpowiedź bezpośrednio adresuje intencję pytania użytkownika?~~
  - [x] ~~**C. Sędzia Bezpieczeństwa (Safety Judge):** Sprawdza odporność na próby jailbreaku i wyciek wrażliwych danych.~~

### ~~3. Implementacja w kodzie z wymuszeniem JSON (Structured Outputs)~~
- [x] ~~Używamy silnika structured outputs z temperaturą 0.0, aby zagwarantować powtarzalność.~~

```python
~~class MetricVerdict(BaseModel):~~
~~    extracted_claims: list[str] = Field(description="Lista atomowych faktów wyciągniętych z odpowiedzi.")~~
~~    reasoning: str = Field(description="Analiza krok po kroku w oparciu o kryteria.")~~
~~    score: float = Field(description="Ocena zdefiniowana w rubryce: 0.0, 0.5 lub 1.0")~~
```

### ~~4. Kalibracja: tani model sędziowski vs drogi model~~
- [x] ~~W CI/CD zależy Ci na czasie i kosztach: Użyj szybkiego i taniego modelu (np. gpt-4o-mini, gemini-1.5-flash), ale skalibruj go z modelem wzorcowym i człowiekiem (czym zajmiemy się w Fazie 4).~~