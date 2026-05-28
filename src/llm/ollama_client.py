"""Async Ollama client with Pydantic-schema-constrained JSON output."""

from __future__ import annotations

from typing import TypeVar

import ollama
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class OllamaClient:
    def __init__(
        self,
        model: str = "llama3.1:8b",
        host: str = "http://localhost:11434",
    ) -> None:
        self.model = model
        self.client = ollama.AsyncClient(host=host)

    async def chat(self, system: str, user: str, temperature: float = 0.4) -> str:
        response = await self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            options={"temperature": temperature},
        )
        return response["message"]["content"]

    async def complete(self, prompt: str, temperature: float = 0.4) -> str:
        """Single-prompt completion. Satisfies src.llm.base.LLMClient Protocol —
        Agent 1 (Triage) uses this since it builds one composite prompt."""
        response = await self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": temperature},
        )
        return response["message"]["content"]

    async def complete_json(
        self,
        prompt: str,
        schema: type[T],
        temperature: float = 0.3,
    ) -> T:
        """Schema-enforced single-prompt completion via Ollama's format=schema.
        Eliminates enum-hallucination crashes (Llama can't output values outside
        the schema's enum constraints)."""
        response = await self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            format=schema.model_json_schema(),
            options={"temperature": temperature},
        )
        return schema.model_validate_json(response["message"]["content"])

    async def chat_json(
        self,
        system: str,
        user: str,
        schema: type[T],
        temperature: float = 0.3,
    ) -> T:
        response = await self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            format=schema.model_json_schema(),
            options={"temperature": temperature},
        )
        return schema.model_validate_json(response["message"]["content"])