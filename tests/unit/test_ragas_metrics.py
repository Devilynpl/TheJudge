"""Unit tests for RagasResult and RagasEvaluator."""

import pytest
from judgekit.metrics.ragas_metrics import RagasEvaluator, RagasResult


@pytest.mark.asyncio
async def test_ragas_evaluator_grounded_answer():
    evaluator = RagasEvaluator()

    query = "Ile wynosi okres gwarancji baterii w robocie?"
    contexts = ["Sekcja 4.2: Okres gwarancji na baterię wynosi 24 miesiące."]
    answer = "Okres gwarancji na baterię wynosi dokładnie 24 miesiące."
    ref_answer = "Bateria objęta jest 24-miesięczną gwarancją."

    result = await evaluator.a_evaluate(
        query=query,
        answer=answer,
        contexts=contexts,
        reference_answer=ref_answer,
    )

    assert isinstance(result, RagasResult)
    assert result.faithfulness == 1.0
    assert result.answer_relevancy > 0.5
    assert result.context_precision == 1.0
    assert result.context_recall == 1.0


@pytest.mark.asyncio
async def test_ragas_evaluator_hallucination_zero_faithfulness():
    evaluator = RagasEvaluator()

    query = "Jaki jest zasięg urządzenia?"
    contexts = []  # Brak kontekstów
    answer = "Zasięg urządzenia wynosi 500 kilometrów i działa na baterii słonecznej."

    result = await evaluator.a_evaluate(
        query=query,
        answer=answer,
        contexts=contexts,
    )

    assert result.faithfulness == 0.0


@pytest.mark.asyncio
async def test_ragas_evaluator_deterministic_refusal():
    evaluator = RagasEvaluator()

    query = "Czy serwis oferuje darmowy odbiór w niedzielę?"
    contexts = []
    answer = "Dokumentacja nie zawiera informacji na temat odbioru w niedzielę. Nie wiem."

    result = await evaluator.a_evaluate(
        query=query,
        answer=answer,
        contexts=contexts,
    )

    assert result.faithfulness == 1.0
    assert result.answer_relevancy == 1.0


@pytest.mark.asyncio
async def test_ragas_sync_wrapper():
    evaluator = RagasEvaluator()

    result = evaluator.evaluate(
        query="Test query",
        answer="Dokumentacja nie zawiera danych.",
        contexts=[],
    )

    assert isinstance(result, RagasResult)
    assert result.faithfulness == 1.0


@pytest.mark.asyncio
async def test_ragas_empty_answer():
    evaluator = RagasEvaluator()

    result = await evaluator.a_evaluate(
        query="Pytanie",
        answer="",
        contexts=["Kontekst"],
    )

    assert result.faithfulness == 0.0
    assert result.answer_relevancy == 0.0


@pytest.mark.asyncio
async def test_ragas_partial_context_precision():
    evaluator = RagasEvaluator()

    query = "Jak wymienić filtr oleju w silniku?"
    contexts = [
        "Wymiana filtra oleju: odkręć obudowę i wymień wkład filtrujący silnika.",
        "Pogoda jutro będzie deszczowa z silnym wiatrem.",
    ]
    answer = "Należy odkręcić obudowę filtra oleju w silniku i wymienić wkład."

    result = await evaluator.a_evaluate(
        query=query,
        answer=answer,
        contexts=contexts,
    )

    assert result.context_precision == 0.5  # 1 out of 2 chunks relevant
    assert result.faithfulness == 1.0

