"""Persistent ChromaDB wrapper with Ollama-backed embeddings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
import ollama
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings


class OllamaEmbedder(EmbeddingFunction[Documents]):
    """Chroma-compatible embedding function backed by Ollama's batch embed API."""

    def __init__(
        self,
        model: str = "nomic-embed-text",
        host: str = "http://localhost:11434",
    ) -> None:
        self.model = model
        self.client = ollama.Client(host=host)

    def __call__(self, input: Documents) -> Embeddings:
        response = self.client.embed(model=self.model, input=list(input))
        return list(response["embeddings"])

    def name(self) -> str:
        return f"ollama-{self.model}"


class ChromaStore:
    def __init__(
        self,
        collection_name: str,
        persist_dir: str | Path = "data/chroma",
        embedder: OllamaEmbedder | None = None,
    ) -> None:
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedder or OllamaEmbedder(),
        )

    def add(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)

    def query(
        self,
        text: str,
        k: int = 3,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        result = self.collection.query(query_texts=[text], n_results=k, where=where)
        ids = result["ids"][0]
        docs = result["documents"][0]
        metas = result["metadatas"][0] if result.get("metadatas") else [{}] * len(ids)
        dists = result["distances"][0] if result.get("distances") else [None] * len(ids)
        return [
            {"id": ids[i], "document": docs[i], "metadata": metas[i], "distance": dists[i]}
            for i in range(len(ids))
        ]

    def existing_ids(self) -> set[str]:
        return set(self.collection.get()["ids"])

    def count(self) -> int:
        return self.collection.count()