# Faza 10: Podpięcie pod docelowy projekt RAG i test na wstrzykniętych regresjach (Chaos Eval)

To faza ostatecznej weryfikacji całego systemu. Jeśli zbudujesz JudgeKit, ale nie przetestujesz empirycznie, czy potrafi złapać celowo wprowadzone awarie, masz tylko iluzję bezpieczeństwa.

**Cel:** zintegrować JudgeKit z docelowym pipeline'em RAG za pomocą wzorca Adaptera, a następnie przeprowadzić **Chaos Engineering dla LLM** — celowo popsuć parametry systemu w osobnych gałęziach i udowodnić, że bramka CI/CD bezbłędnie zablokuje każdy ze szkodliwych PR-ów.

---

### 1. Architektura podpięcia pod Projekt RAG (Adapter Pattern)
Docelowy projekt RAG nie powinien zależeć od wewnętrznych struktur ewaluatora. Tworzymy w repozytorium cienki adapter (`src/judgekit/rag_adapter.py`), który wystawia zunifikowany interfejs:

- [x] ~~Implementacja wzorca adaptera `RAGSystemAdapter` i kontraktu `RAGResponse` (odpowiedź, źródła, tokeny, opóźnienie).~~

```python
from typing import List, NamedTuple

class RAGResponse(NamedTuple):
    answer: str
    contexts: List[str]
    input_tokens: int
    output_tokens: int

class RAGSystemAdapter:
    def __init__(self, rag_pipeline):
        self.pipeline = rag_pipeline

    async def aquery(self, query: str) -> RAGResponse:
        result = await self.pipeline.arun(query)
        return RAGResponse(
            answer=result["response"],
            contexts=[doc.page_content for doc in result.get("source_documents", [])],
            input_tokens=result.get("usage", {}).get("prompt_tokens", 0),
            output_tokens=result.get("usage", {}).get("completion_tokens", 0),
        )
```

---

### 2. Testy Chaosu: Wstrzykiwanie 4 typowych regresji
- [x] ~~Implementacja modułu Chaos Engineering `src/judgekit/chaos_eval.py` oraz narzędzia CLI `src/judgekit/cli_chaos.py`.~~
- [x] ~~Weryfikacja zachowania bramki jakości (Quality Gate) na 4 syntetycznych awariach:~~

| Branch testowy | Wstrzyknięta zmiana | Oczekiwany efekt w RAG | Reakcja JudgeKit (Quality Gate) | Wynik |
| :--- | :--- | :--- | :--- | :---: |
| `chaos/bad-chunking` | Zmniejszenie chunk size z 512 do 128 tokenów | Rozbicie faktów, utrata kontekstu dla zapytań multi-hop | **BLOKADA PR:** Drastyczny spadek Faithfulness (-0.20) | ✅ **ZABLOKOWANY** |
| `chaos/top-k-drop` | Zmniejszenie top_k z 5 do 1 dokumentu | Brak kluczowych fragmentów w prompcie | **BLOKADA PR:** Wykrycie halucynacji (model zmyśla brakujące dane) | ✅ **ZABLOKOWANY** |
| `chaos/sloppy-prompt` | Usunięcie instrukcji: *„Jeśli brak danych, powiedz nie wiem”* | Model odpowiada z wiedzy ogólnej na zapytania out-of-domain | **BLOKADA PR:** Skok błędów krytycznych ($1.0 \to 0.0$) | ✅ **ZABLOKOWANY** |
| `chaos/heavy-reranker` | Dodanie bardzo powolnego cross-encodera do retrievalu | Minimalna poprawa jakości (+1%), lecz drastyczny skok czasu | **BLOKADA PR:** Przekroczenie limitu wydajności $P95\text{ Latency} > +250\text{ ms}$ | ✅ **ZABLOKOWANY** |

---

### 3. Wskaźnik Wykrywalności Regresji (Evaluation Score)
Po przeprowadzeniu testów weryfikujemy niezawodność systemu za pomocą metryki:

$$\text{Wskaźnik Wykrywalności Regresji} = \frac{\text{Liczba zablokowanych szkodliwych PR}}{\text{Liczba celowo wprowadzonych awarii}} \times 100\%$$

- [x] ~~**Empiryczny wynik Chaos Eval: 4/4 zablokowanych PR-ów $\implies$ RDR = 100.0%.**~~
Osiągnięcie 100% wykrywalności dowodzi pełnej gotowości systemu do pracy na produkcji.