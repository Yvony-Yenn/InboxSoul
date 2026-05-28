"""Unit tests for FewShotRetriever — confirms it filters discarded drafts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.hermes.feedback_store import COLLECTION_NAME, FeedbackWriter
from src.hermes.retriever import FewShotRetriever
from src.hermes.schemas import FeedbackRecord, FewShotExample, UserAction
from src.pipeline.schemas import CleanedEmail
from src.rag.chroma_store import ChromaStore
from tests.unit.test_chroma_store import FakeEmbedder


@pytest.fixture
def seeded_store(tmp_path: Path) -> ChromaStore:
    store = ChromaStore(
        collection_name=COLLECTION_NAME,
        persist_dir=tmp_path / "chroma",
        embedder=FakeEmbedder(),
    )
    writer = FeedbackWriter(store)
    for id_, action, body in [
        ("r1", UserAction.SENT, "can you review my PR"),
        ("r2", UserAction.EDITED_THEN_SENT, "please look at the auth bug"),
        ("r3", UserAction.DISCARDED, "spam-y pitch we threw away"),
    ]:
        writer.record(
            FeedbackRecord(
                id=id_,
                incoming_email=CleanedEmail(
                    message_id=id_,
                    sender="x@y.com",
                    subject="s",
                    body=body,
                    received_at=datetime(2026, 5, 25, 9, 30),
                ),
                draft_v0=f"draft for {id_}",
                final_sent=f"final for {id_}",
                user_action=action,
                created_at=datetime(2026, 5, 25, 10, 0),
            )
        )
    return store


def test_retrieve_returns_few_shot_examples(seeded_store: ChromaStore) -> None:
    retriever = FewShotRetriever(seeded_store)
    hits = retriever.retrieve("PR review please", k=5)
    assert all(isinstance(h, FewShotExample) for h in hits)
    assert all(h.incoming and h.reply for h in hits)


def test_retrieve_filters_discarded(seeded_store: ChromaStore) -> None:
    retriever = FewShotRetriever(seeded_store)
    hits = retriever.retrieve("anything", k=10)
    replies = {h.reply for h in hits}
    assert "final for r3" not in replies
    assert replies <= {"final for r1", "final for r2"}


def test_retrieve_respects_k(seeded_store: ChromaStore) -> None:
    retriever = FewShotRetriever(seeded_store)
    hits = retriever.retrieve("anything", k=1)
    assert len(hits) == 1