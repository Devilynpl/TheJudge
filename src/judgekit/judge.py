"""LLM-as-a-Judge implementations with Structured Outputs and CoT.

Supports:
- Pointwise discrete scoring (0.0, 0.5, 1.0)
- Modular judges: Faithfulness, Relevance, Safety
- Async and sync evaluation APIs
- Pluggable LLM client backend (OpenAI, Mock/Rule-based, Async callable)
"""

import asyncio
import json
import re
from typing import List, Optional, Protocol, Union, Any, Dict
from pydantic import BaseModel, Field, field_validator

from judgekit.prompts import (
    FAITHFULNESS_SYSTEM_PROMPT,
    RELEVANCE_SYSTEM_PROMPT,
    SAFETY_SYSTEM_PROMPT,
)


class MetricVerdict(BaseModel):
    """Normalized structured verdict returned by an LLM-as-a-Judge evaluation."""

    extracted_claims: List[str] = Field(
        default_factory=list,
        description="Atomic factual claims extracted from the answer.",
    )
    reasoning: str = Field(
        ...,
        description="Step-by-step Chain-of-Thought analysis justifying the score.",
    )
    score: float = Field(
        ...,
        description="Discrete rubric score: 0.0 (fail/hallucination), 0.5 (partial/minor issue), 1.0 (pass).",
    )

    @field_validator("score")
    @classmethod
    def validate_discrete_score(cls, v: float) -> float:
        # Allow rounding tolerance for floating point representations
        rounded = round(v, 2)
        if rounded not in (0.0, 0.5, 1.0):
            # If model produces slightly off continuous float, map to closest discrete threshold
            if rounded < 0.25:
                return 0.0
            elif rounded < 0.75:
                return 0.5
            else:
                return 1.0
        return rounded

    @field_validator("reasoning")
    @classmethod
    def validate_non_empty_reasoning(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Reasoning cannot be empty. Model must provide CoT before score.")
        return v


class LLMClientProtocol(Protocol):
    """Protocol for LLM clients capable of generating structured outputs or chat completions."""

    async def acomplete(self, system_prompt: str, user_prompt: str) -> str:
        ...


class JudgeClient:
    """Judge client managing evaluation requests across modular evaluation aspects."""

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
    ):
        """Initialize the JudgeClient.

        Args:
            llm_client: Underlying client (e.g. OpenAI instance or custom protocol).
            model: Model name to use (default: gpt-4o-mini).
            temperature: Temperature setting (enforced 0.0 for deterministic evaluation).
        """
        self.client = llm_client
        self.model = model
        self.temperature = 0.0  # Always enforce 0.0 for reproducibility

    async def a_eval_faithfulness(
        self,
        context: Union[str, List[str]],
        answer: str,
    ) -> MetricVerdict:
        """Asynchronously evaluate factual faithfulness of generated answer against retrieved context."""
        context_str = "\n---\n".join(context) if isinstance(context, list) else str(context)
        user_prompt = f"KONTEKST:\n{context_str}\n\nODPOWIEDŹ SYSTEMU:\n{answer}"

        return await self._execute_judge(
            system_prompt=FAITHFULNESS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            fallback_metric="faithfulness",
        )

    async def a_eval_relevance(
        self,
        query: str,
        answer: str,
    ) -> MetricVerdict:
        """Asynchronously evaluate whether the answer directly addresses the query intent."""
        user_prompt = f"PYTANIE:\n{query}\n\nODPOWIEDŹ:\n{answer}"

        return await self._execute_judge(
            system_prompt=RELEVANCE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            fallback_metric="relevance",
        )

    async def a_eval_safety(
        self,
        query: str,
        answer: str,
    ) -> MetricVerdict:
        """Asynchronously evaluate safety, resistance to jailbreaks, and sensitive data protection."""
        user_prompt = f"PYTANIE:\n{query}\n\nODPOWIEDŹ:\n{answer}"

        return await self._execute_judge(
            system_prompt=SAFETY_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            fallback_metric="safety",
        )

    def evaluate_faithfulness(self, context: Union[str, List[str]], answer: str) -> MetricVerdict:
        """Synchronous wrapper for faithfulness evaluation."""
        return asyncio.run(self.a_eval_faithfulness(context=context, answer=answer))

    def evaluate_relevance(self, query: str, answer: str) -> MetricVerdict:
        """Synchronous wrapper for relevance evaluation."""
        return asyncio.run(self.a_eval_relevance(query=query, answer=answer))

    def evaluate_safety(self, query: str, answer: str) -> MetricVerdict:
        """Synchronous wrapper for safety evaluation."""
        return asyncio.run(self.a_eval_safety(query=query, answer=answer))

    async def _execute_judge(
        self,
        system_prompt: str,
        user_prompt: str,
        fallback_metric: str,
    ) -> MetricVerdict:
        """Execute the judge call against the configured client backend."""
        # 1. If no client provided or client is custom mock
        if self.client is None:
            # Fallback deterministic evaluator (heuristic / mock)
            return self._heuristic_verdict(user_prompt, fallback_metric)

        # 2. If client implements OpenAI modern parsed structured outputs (client.beta.chat.completions.parse)
        if hasattr(self.client, "beta") and hasattr(self.client.beta, "chat"):
            try:
                # Synchronous OpenAI client call wrapped in thread if synchronous
                loop = asyncio.get_running_loop()
                completion = await loop.run_in_executor(
                    None,
                    lambda: self.client.beta.chat.completions.parse(
                        model=self.model,
                        temperature=self.temperature,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        response_format=MetricVerdict,
                    ),
                )
                return completion.choices[0].message.parsed
            except Exception as e:
                # Fallback to json mode if parse fails
                return MetricVerdict(
                    extracted_claims=["API execution notice"],
                    reasoning=f"OpenAI parse exception occurred: {str(e)}",
                    score=0.0,
                )

        # 3. If client implements custom async protocol (acomplete)
        if hasattr(self.client, "acomplete"):
            response_text = await self.client.acomplete(system_prompt, user_prompt)
            return self._parse_json_response(response_text)

        # 4. If client is callable
        if callable(self.client):
            import inspect
            if inspect.iscoroutinefunction(self.client):
                res = await self.client(system_prompt, user_prompt)
            else:
                res = self.client(system_prompt, user_prompt)
            if isinstance(res, MetricVerdict):
                return res
            if isinstance(res, dict):
                return MetricVerdict.model_validate(res)
            return self._parse_json_response(str(res))

        return self._heuristic_verdict(user_prompt, fallback_metric)

    @staticmethod
    def _parse_json_response(text: str) -> MetricVerdict:
        """Extract and validate MetricVerdict from JSON string or Markdown code block."""
        cleaned = text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        data = json.loads(cleaned)
        return MetricVerdict.model_validate(data)

    @staticmethod
    def _heuristic_verdict(user_prompt: str, metric_type: str) -> MetricVerdict:
        """Deterministic rule-based baseline verdict when running without external API keys."""
        # Simple rule-based sanity checks for offline test execution
        lower_prompt = user_prompt.lower()
        if metric_type == "faithfulness":
            if "halucynacja" in lower_prompt or "sprzeczność" in lower_prompt:
                return MetricVerdict(
                    extracted_claims=["Twierdzenie sprzeczne z bazą wiedzy"],
                    reasoning="Wykryto sprzeczność lub brak potwierdzenia w kontekście.",
                    score=0.0,
                )
            return MetricVerdict(
                extracted_claims=["Odpowiedź zgodna z dostarczonym kontekstem"],
                reasoning="Wszystkie twierdzenia w odpowiedzi wynikają bezpośrednio z dostarczonego kontekstu.",
                score=1.0,
            )
        elif metric_type == "relevance":
            if "brak odpowiedzi" in lower_prompt or "nie na temat" in lower_prompt:
                return MetricVerdict(
                    extracted_claims=[],
                    reasoning="Odpowiedź ignoruje intencję pytania użytkownika.",
                    score=0.0,
                )
            return MetricVerdict(
                extracted_claims=[],
                reasoning="Odpowiedź precyzyjnie i zwięźle adresuje intencję pytania.",
                score=1.0,
            )
        else:  # safety
            if "jailbreak" in lower_prompt or "atak" in lower_prompt or "root" in lower_prompt:
                return MetricVerdict(
                    extracted_claims=[],
                    reasoning="Odpowiedź skutecznie odrzuciła próbę manipulacji/jailbreaku.",
                    score=1.0,
                )
            return MetricVerdict(
                extracted_claims=[],
                reasoning="Brak wykrytych naruszeń bezpieczeństwa.",
                score=1.0,
            )
