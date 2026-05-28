"""Unit tests for ChromaStore with a deterministic fake embedder."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from src.rag.chroma_store import ChromaStore


class FakeEmbedder(EmbeddingFunction[Documents]):
    """Deterministic hash-based embedder — 32-dim vectors, no network."""

    def __init__(self) -> None:
        pass

    def __call__(self, input: Documents) -> Embeddings:
        return [self._embed(t) for t in input]

    def _embed(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).digest()
        return [(b / 127.5) - 1.0 for b in h]

    def name(self) -> str:
        return "fake-sha256"


@pytest.fixture
def store(tmp_path: Path) -> ChromaStore:
    return ChromaStore(
        collection_name="test",
        persist_dir=tmp_path / "chroma",
        embedder=FakeEmbedder(),
    )


def test_add_and_count(store: ChromaStore) -> None:
    store.add(
        ids=["a", "b"],
        documents=["hello world", "goodbye world"],
        metadatas=[{"tag": "x"}, {"tag": "y"}],
    )
    assert store.count() == 2


def test_query_returns_flat_dicts(store: ChromaStore) -> None:
    store.add(ids=["a"], documents=["hello world"], metadatas=[{"tag": "x"}])
    hits = store.query("hello world", k=1)
    assert len(hits) == 1
    assert hits[0]["id"] == "a"
    assert hits[0]["document"] == "hello world"
    assert hits[0]["metadata"] == {"tag": "x"}


def test_existing_ids_roundtrip(store: ChromaStore) -> None:
    store.add(ids=["a", "b"], documents=["one", "two"])
    assert store.existing_ids() == {"a", "b"}


def test_query_respects_where_filter(store: ChromaStore) -> None:
    store.add(
        ids=["a", "b", "c"],
        documents=["foo", "bar", "baz"],
        metadatas=[{"cat": "x"}, {"cat": "y"}, {"cat": "x"}],
    )
    hits = store.query("foo", k=5, where={"cat": "x"})
    assert {h["id"] for h in hits} == {"a", "c"}