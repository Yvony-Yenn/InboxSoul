"""Unit tests for StyleRetriever and seed_from_jsonl."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.rag.chroma_store import ChromaStore
from src.rag.style_retriever import StyleRetriever, seed_from_jsonl
from tests.unit.test_chroma_store import FakeEmbedder

FIXTURE = Path(__file__).parents[1] / "fixtures" / "past_replies.jsonl"


@pytest.fixture
def store(tmp_path: Path) -> ChromaStore:
    return ChromaStore(
        collection_name="past_replies",
        persist_dir=tmp_path / "chroma",
        embedder=FakeEmbedder(),
    )


def test_seed_loads_all_records(store: ChromaStore) -> None:
    added = seed_from_jsonl(store, FIXTURE)
    fixture_count = sum(1 for line in FIXTURE.read_text().splitlines() if line.strip())
    assert added == fixture_count
    assert store.count() == fixture_count


def test_seed_is_idempotent(store: ChromaStore) -> None:
    first = seed_from_jsonl(store, FIXTURE)
    second = seed_from_jsonl(store, FIXTURE)
    assert first > 0
    assert second == 0
    assert store.count() == first


def test_retrieve_returns_user_reply_strings(store: ChromaStore) -> None:
    seed_from_jsonl(store, FIXTURE)
    retriever = StyleRetriever(store)
    anchors = retriever.retrieve("can you confirm thursday's meeting time?", k=3)
    assert 1 <= len(anchors) <= 3
    assert all(isinstance(a, str) and a for a in anchors)


def test_retrieve_with_category_filter(store: ChromaStore) -> None:
    seed_from_jsonl(store, FIXTURE)
    retriever = StyleRetriever(store)
    anchors = retriever.retrieve("any plans this weekend?", category="personal", k=5)
    personal_replies = {
        "down — 7pm? I'll text you when I'm headed over",
        "haha yeah I can swing by around 10. how much stuff are we talking?",
    }
    assert set(anchors).issubset(personal_replies)