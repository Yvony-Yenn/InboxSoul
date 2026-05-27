"""Provider-agnostic LLM client interface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Minimal async contract. Concrete implementations live in src/llm/<provider>.py."""

    async def complete(self, prompt: str) -> str:
        ...
