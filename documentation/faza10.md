Faza 10: Podpięcie pod docelowy projekt RAG i test na wstrzykniętych regresjach (Chaos Eval)To faza weryfikacji całego systemu. Jeśli zbudujesz JudgeKit, ale nie przetestujesz, czy potrafi złapać celowo wprowadzone awarie, masz tylko iluzję bezpieczeństwa.Cel: zintegrować JudgeKit z docelowym pipeline'em RAG, a następnie przeprowadzić Chaos Engineering dla LLM — celowo popsuć parametry systemu w osobnych branchach i udowodnić, że bramka CI/CD bezbłędnie zablokuje każdy z nich.1. Architektura podpięcia pod Projekt RAG (Adapter Pattern)Docelowy projekt RAG nie powinien wiedzieć nic o strukturze sędziego. Tworzymy w repozytorium cienki adapter (rag_adapter.py), który wystawia zunifikowany interfejs:Pythonfrom typing import NamedTuple, List

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
            contexts=[doc.page_content for doc in result["source_documents"]],
            input_tokens=result.get("usage", {}).get("prompt_tokens", 0),
            output_tokens=result.get("usage", {}).get("completion_tokens", 0)
        )
2. Testy Chaosu: Wstrzykiwanie 4 typowych regresjiZakładasz 4 eksperymentalne branche gita i wystawiasz z nich Pull Requesty do main. Każdy z nich symuluje częsty błąd inżynierski:Branch testowyWstrzyknięta zmianaOczekiwany efekt w RAGCo musi zrobić JudgeKit?chaos/bad-chunkingZmniejszenie chunk size z 512 do 128 tokenówRozbicie faktów, utrata kontekstu dla zapytań multi-hopBLOKADA PR: Drastyczny spadek Faithfulness w kategorii Multi-hopchaos/top-k-dropZmniejszenie top_k z 5 do 1 dokumentuBrak kluczowych fragmentów w promptcieBLOKADA PR: Wykrycie halucynacji (model zmyśla brakujące dane)chaos/sloppy-promptUsunięcie instrukcji: „Jeśli nie ma w tekście, powiedz nie wiem”Model odpowiada z wiedzy ogólnej na zapytania out-of-domainBLOKADA PR: Skok błędów krytycznych ($1.0 \to 0.0$) na pytaniach Unanswerablechaos/heavy-rerankerDodanie bardzo wolnego cross-encodera do retrievaluPoprawa jakości o +1%, ale drastyczny wzrost czasuBLOKADA PR: Przekroczenie limitu $P95\text{ Latency} > +250\text{ ms}$3. Obliczenie ostatecznej metryki: % Złapanych RegresjiPo przeprowadzeniu testów weryfikujesz skuteczność systemu za pomocą prostego wzoru:$$\text{Wskaźnik Wykrywalności Regresji} = \frac{\text{Liczba zablokowanych szkodliwych PR}}{\text{Liczba celowo wprowadzonych awarii}} \times 100\%$$