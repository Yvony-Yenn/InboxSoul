"""IngestionSource Protocol — every provider (IMAP, Gmail API, Graph API) implements this."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.pipeline.schemas import CleanedEmail


@runtime_checkable
class IngestionSource(Protocol):
    async def fetch_unread(self, limit: int = 50) -> list[CleanedEmail]: ...