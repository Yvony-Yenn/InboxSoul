"""FeedbackWriter — persists user review events into the hermes_feedback collection."""

from __future__ import annotations

from src.hermes.schemas import FeedbackRecord
from src.rag.chroma_store import ChromaStore

COLLECTION_NAME = "hermes_feedback"


class FeedbackWriter:
    def __init__(self, store: ChromaStore) -> None:
        self.store = store

    def record(self, feedback: FeedbackRecord) -> None:
        self.store.add(
            ids=[feedback.id],
            documents=[feedback.incoming_email.body],
            metadatas=[
                {
                    "final_sent": feedback.final_sent,
                    "draft_v0": feedback.draft_v0,
                    "user_action": feedback.user_action.value,
                    "sender": feedback.incoming_email.sender,
                    "created_at": feedback.created_at.isoformat(),
                }
            ],
        )