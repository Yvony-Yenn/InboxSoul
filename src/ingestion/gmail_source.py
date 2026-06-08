"""GmailSource — Gmail API implementation of IngestionSource.

Reads unread inbox messages not yet triaged (excludes the InboxSoul/Triaged marker
label that the executor adds) so the poller is idempotent across runs and never
re-reads mail the user has already read. The returned CleanedEmail.message_id is the
Gmail API message id, so the executor can act on it.

Read-only: this module never modifies labels. All mailbox mutation lives in the
executor (src/review/executor.py).
"""

from __future__ import annotations

import asyncio
import base64

from src.ingestion.base import IngestionSource
from src.ingestion.cleaner import clean_message
from src.ingestion.raw_parser import parse_raw_message
from src.pipeline.schemas import CleanedEmail

TRIAGED_LABEL = "InboxSoul/Triaged"
DEFAULT_QUERY = f"is:unread in:inbox -label:{TRIAGED_LABEL}"


class GmailSource(IngestionSource):
    def __init__(self, service, query: str = DEFAULT_QUERY) -> None:
        self._svc = service
        self._query = query

    async def fetch_unread(self, limit: int = 50) -> list[CleanedEmail]:
        return await asyncio.to_thread(self._fetch, limit)

    def _fetch(self, limit: int) -> list[CleanedEmail]:
        listed = (
            self._svc.users()
            .messages()
            .list(userId="me", q=self._query, maxResults=limit)
            .execute()
        )
        results: list[CleanedEmail] = []
        for ref in listed.get("messages", []):
            msg = (
                self._svc.users()
                .messages()
                .get(userId="me", id=ref["id"], format="raw")
                .execute()
            )
            raw = base64.urlsafe_b64decode(msg["raw"])
            cleaned = clean_message(parse_raw_message(raw))
            results.append(cleaned.model_copy(update={"message_id": ref["id"]}))
        return results