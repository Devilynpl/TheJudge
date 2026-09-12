"""Protocol definitions and standard contracts for external evaluation targets in JudgeKit.

Enables unified, asynchronous evaluation across different AI systems:
- RAG pipelines (DocGround)
- Autonomous research agents (BriefAgent)
- Custom LLM workflows
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from pydantic import BaseModel, Field


class TargetOutput(BaseModel):
    """Standardized output contract returned by any target system adapter."""

    answer: str = Field(..., description="Generated answer, summary, or report.")
    contexts: List[str] = Field(
        default_factory=list,
        description="Retrieved document contexts, evidence snippets, or raw observations.",
    )
    input_tokens: int = Field(default=0, ge=0, description="Number of prompt/input tokens consumed.")
    output_tokens: int = Field(default=0, ge=0, description="Number of output/completion tokens consumed.")
    latency_ms: float = Field(default=0.0, ge=0.0, description="Execution latency in milliseconds.")
    cost_usd: float = Field(default=0.0, ge=0.0, description="Estimated or exact cost in USD.")

    # Extended agent/tool metadata
    step_count: Optional[int] = Field(default=None, description="Number of execution steps / FSM transitions taken.")
    status: Optional[str] = Field(default=None, description="Target execution status (e.g. COMPLETED, UNVERIFIABLE_COMPANY).")
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list, description="Structured log of tool executions.")
    tool_error_recovery_rate: Optional[float] = Field(default=None, description="Fraction of tool errors recovered via retries/circuit breaker.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary target-specific metadata.")


@runtime_checkable
class BaseTargetAdapter(Protocol):
    """Structural protocol that any target system must implement to be evaluated by JudgeKit."""

    async def run_query(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> TargetOutput:
        """Execute a single query or test case asynchronously against the target system.

        Args:
            query: The user prompt, search query, or company name.
            metadata: Optional test case metadata (e.g., category, domain, expected behavior).

        Returns:
            TargetOutput: Normalized evaluation contract.
        """
        ...
