"""AWS Bedrock LLM Client Adapter for JudgeKit.

Connects TheJudge evaluation suite to Anthropic Claude 3.5 / 4.5 Sonnet on AWS Bedrock
for high-accuracy, zero-hallucination continuous quality gate benchmarking.
"""

import os
import json
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("judgekit.bedrock")


class BedrockJudgeClient:
    """Judge client adapter connecting JudgeKit to Anthropic Claude on AWS Bedrock."""

    def __init__(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: Optional[str] = None,
        model_id: Optional[str] = None,
    ):
        self.aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        self.region_name = region_name or os.getenv("AWS_REGION", "eu-central-1")
        raw_model = model_id or os.getenv(
            "AWS_BEDROCK_MODEL_ID",
            "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
        )
        self.model_id = self._normalize_model_id(raw_model, self.region_name)
        self._client = None

    @staticmethod
    def _normalize_model_id(mid: str, region: str) -> str:
        mid = mid.strip()
        if mid.startswith("arn:aws:bedrock:") or mid.startswith("eu.") or mid.startswith("us.") or mid.startswith("global."):
            return mid
        if mid.startswith("anthropic.claude-"):
            prefix = "eu." if "eu-" in region else "global."
            return f"{prefix}{mid}"
        return mid

    def is_configured(self) -> bool:
        return bool(self.aws_access_key_id and self.aws_secret_access_key and self.model_id)

    def _get_client(self):
        if self._client is None:
            import boto3

            session = boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region_name,
            )
            self._client = session.client("bedrock-runtime")
        return self._client

    async def acomplete(self, system_prompt: str, user_prompt: str) -> str:
        """Satisfies LLMClientProtocol for JudgeClient."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.complete_sync(system_prompt, user_prompt)
        )

    def complete_sync(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        prompt_with_format = (
            f"{system_prompt}\n\n"
            "Format wyjściowy JSON:\n"
            "{\n"
            '  "extracted_claims": ["twierdzenie 1", "twierdzenie 2"],\n'
            '  "reasoning": "Szczegółowe uzasadnienie CoT...",\n'
            '  "score": 1.0\n'
            "}\nZwróć WYŁĄCZNIE poprawny obiekt JSON, bez znaczników markdown."
        )

        response = client.converse(
            modelId=self.model_id,
            system=[{"text": prompt_with_format}],
            messages=[{"role": "user", "content": [{"text": user_prompt}]}],
            inferenceConfig={"maxTokens": 1024, "temperature": 0.0},
        )
        output_msg = response.get("output", {}).get("message", {})
        text = ""
        for c in output_msg.get("content", []):
            if "text" in c:
                text += c["text"]
        return text
