"""FewShotRetriever — surface past (incoming, final_sent) pairs from real review history.

Filters out DISCARDED drafts: only SENT / EDITED_THEN_SENT are positive signals.
"""

from __future__ import annotations

from src.hermes.schemas import FewShotExample, UserAction
from src.rag.chroma_store import ChromaStore


class FewShotRetriever:
    def __init__(self, store: ChromaStore) -> None:
        self.store = store

    def retrieve(self, incoming_body: str, k: int = 3) -> list[FewShotExample]:
        hits = self.store.query(
            text=incoming_body,
            k=k,
            where={
                "user_action": {
                    "$in": [UserAction.SENT.value, UserAction.EDITED_THEN_SENT.value]
                }
            },
        )
        return [
            FewShotExample(incoming=h["document"], reply=h["metadata"]["final_sent"])
            for h in hits
            if h["metadata"].get("final_sent")
        ]