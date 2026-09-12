Faza 3: Implementacja i kalibracja Sędziego (LLM-as-a-Judge)

Sędzia to serce systemu. Jeśli sędzia jest niestabilny, cały proces CI/CD traci sens, bo deweloperzy przestaną ufać wynikom.

Cel: zaimplementować wyspecjalizowane prompty sędziowskie, wymusić determinizm strukturalny i wyeliminować typowe błędy poznawcze modeli (LLM biases).

1. Złote zasady projektowania promptu sędziego

Większość implementacji LLM-as-a-Judge zawodzi przez 4 typowe zjawiska:

    Position Bias: model faworyzuje pierwszą z prezentowanych opcji (w testach A/B).

    Verbosity Bias: model wyżej ocenia odpowiedzi długie i kwieciste, nawet jeśli zawierają błędy.

    Self-Enhancement Bias: model GPT woli odpowiedzi wygenerowane przez GPT, a Claude przez Claude'a.

    Score Compression: model unika ocen skrajnych i daje wszystkim 3/5 lub 4/5.

Rozwiązanie inżynierskie:

    Ocenianie bezwzględne (ang. pointwise scoring) na znormalizowanych rubrykach zamiast nieprecyzyjnych skali gwiazdkowych.

    Narzucenie skali binarnej (0 lub 1) lub wąskiej skali dyskretnej (0.0, 0.5, 1.0), popartej definicją dla każdego progu.

    Chain-of-Thought (CoT) przed werdyktem: model najpierw wypisuje fakty, potem sprawdza sprzeczności, a na końcu decyduje o nocie.

2. Trzy niezależne prompty sędziowskie (Modular Judges)

Nie wrzucaj wszystkiego do jednego promptu. Jeden sędzia = jedna odpowiedzialność.
A. Sędzia Wierności (Faithfulness / Hallucination Judge)

Sprawdza wyłącznie: Czy każde twierdzenie w odpowiedzi wynika bezpośrednio z dostarczonego kontekstu?
Plaintext

Jesteś bezstronnym audytorem wierności faktograficznej (Faithfulness Judge).

Twoim zadaniem jest ocena, czy Odpowiedź jest całkowicie poparta przez podany Kontekst.
Zignoruj własną wiedzę o świecie. Jeśli fakt jest prawdziwy w świecie realnym, 
ale NIE MA go w Kontekście, traktujesz go jako NIEPOPRAWNY.

KROKI OCENY:
1. Rozbij Odpowiedź na pojedyncze twierdzenia faktograficzne (claims).
2. Dla każdego twierdzenia wskaż, czy znajduje ono bezpośrednie potwierdzenie w Kontekście (TAK / NIE).
3. Jeśli choć jedno twierdzenie nie wynika z Kontekstu, podaj krótkie uzasadnienie.

SKALA OCENY:
- 1.0: Wszystkie twierdzenia w Odpowiedzi wynikają bezpośrednio z Kontekstu.
- 0.5: Część twierdzeń wynika z Kontekstu, ale dodano drobne szczegóły niepoparte tekstem (które nie zmieniają sensu).
- 0.0: Odpowiedź zawiera sprzeczności z Kontekstem LUB halucynuje kluczowe fakty.

KONTEKST:
{retrieved_contexts}

ODPOWIEDŹ SYSTEMU:
{generated_answer}

B. Sędzia Trafności (Answer Relevance Judge)

Sprawdza wyłącznie: Czy odpowiedź bezpośrednio adresuje intencję pytania użytkownika? (Nawet w 100% wierny kontekst jest bezużyteczny, jeśli model odpowiedział nie na temat).
Plaintext

Jesteś audytorem trafności odpowiedzi (Relevance Judge).

Twoim zadaniem jest ocena, czy Odpowiedź bezpośrednio i zwięźle odpowiada na Pytanie.
Nie sprawdzasz prawdy faktograficznej – skupiasz się na intencji pytania.

KROKI OCENY:
1. Zidentyfikuj główną intencję Pytania.
2. Zidentyfikuj, czy Odpowiedź zawiera zbędne dygresje, lanie wody lub unika odpowiedzi.
3. Jeśli pytanie zakładało odmowę (brak danych), sprawdź czy model wprost i grzecznie odmówił.

SKALA OCENY:
- 1.0: Odpowiedź precyzyjnie trafia w intencję pytania, brak zbędnego szumu.
- 0.5: Odpowiedź odpowiada na pytanie, ale zawiera niepotrzebne dygresje lub jest niekompletna.
- 0.0: Odpowiedź ignoruje pytanie, zmienia temat lub udziela wymijającej odpowiedzi.

PYTANIE:
{query}

ODPOWIEDŹ:
{generated_answer}

3. Implementacja w kodzie z wymuszeniem JSON (Structured Outputs)

Używamy silnika structured outputs (OpenAI Structured Outputs, Instructor lub native JSON mode w Anthropic/Gemini) z temperaturą 0.0, aby zagwarantować powtarzalność.
Python

from pydantic import BaseModel, Field
from openai import OpenAI

class MetricVerdict(BaseModel):
    extracted_claims: list[str] = Field(
        description="Lista atomowych faktów wyciągniętych z odpowiedzi."
    )
    reasoning: str = Field(
        description="Analiza krok po kroku w oparciu o kryteria."
    )
    score: float = Field(
        description="Ocena zdefiniowana w rubryce: 0.0, 0.5 lub 1.0"
    )

def evaluate_faithfulness(client: OpenAI, context: str, answer: str) -> MetricVerdict:
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",  # Lub mocniejszy model bazowy, np. gpt-4o / sonnet
        temperature=0.0,
        messages=[
            {"role": "system", "content": FAITHFULNESS_SYSTEM_PROMPT},
            {"role": "user", "content": f"KONTEKST:\n{context}\n\nODPOWIEDŹ:\n{answer}"}
        ],
        response_format=MetricVerdict,
    )
    return completion.choices[0].message.parsed

4. Kalibracja: tani model sędziowski vs drogi model

W CI/CD zależy Ci na czasie i kosztach. Uruchomienie 80 testów z sędzią wielkości GPT-4o lub Sonnet 3.5 przy każdym pushu może kosztować dolary i trwać 2 minuty.

    Podejście optymalne: Użyj szybkiego i taniego modelu (np. gpt-4o-mini, gemini-1.5-flash), ale skalibruj go z modelem wzorcowym i człowiekiem (czym zajmiemy się natychmiast w Fazie 4).

    Jeśli sędzia mini zgadza się z człowiekiem w 85–90% przypadków — zostaje w CI.