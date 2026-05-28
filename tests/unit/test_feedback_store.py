"""Unit tests for FeedbackWriter."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.hermes.feedback_store import COLLECTION_NAME, FeedbackWriter
from src.hermes.schemas import FeedbackRecord, UserAction
from src.pipeline.schemas import CleanedEmail
from src.rag.chroma_store import ChromaStore
from tests.unit.test_chroma_store import FakeEmbedder


@pytest.fixture
def writer(tmp_path: Path) -> FeedbackWriter:
    store = ChromaStore(
        collection_name=COLLECTION_NAME,
        persist_dir=tmp_path / "chroma",
        embedder=FakeEmbedder(),
    )
    return FeedbackWriter(store)


def _make_record(id_: str, action: UserAction = UserAction.SENT) -> FeedbackRecord:
    return FeedbackRecord(
        id=id_,
        incoming_email=CleanedEmail(
            message_id=f"msg-{id_}",
            sender="x@y.com",
            subject="hi",
            body=f"body for {id_}",
            received_at=datetime(2026, 5, 25, 9, 30),
        ),
        draft_v0="draft",
        final_sent="final",
        user_action=action,
        created_at=datetime(2026, 5, 25, 10, 0),
    )


def test_record_writes_to_store(writer: FeedbackWriter) -> None:
    writer.record(_make_record("a"))
    assert writer.store.existing_ids() == {"a"}
    assert writer.store.count() == 1


def test_record_preserves_metadata(writer: FeedbackWriter) -> None:
    writer.record(_make_record("a", action=UserAction.EDITED_THEN_SENT))
    hits = writer.store.query("body for a", k=1)
    meta = hits[0]["metadata"]
    assert meta["final_sent"] == "final"
    assert meta["user_action"] == "edited_then_sent"
    assert meta["sender"] == "x@y.com"
    assert "created_at" in meta