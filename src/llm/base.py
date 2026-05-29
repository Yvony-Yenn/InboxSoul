"""Provider-agnostic LLM client interface."""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMClient(Protocol):
    """Minimal async contract. Concrete implementations live in src/llm/<provider>.py."""

    async def complete(self, prompt: str) -> str:
        ...

    async def chat_json(self, *, system: str, user: str, schema: type[T]) -> T:
        """Schema-constrained chat. The provider forces output to satisfy `schema`'s
        JSON Schema at decode time, then returns the validated model instance."""
        ...
