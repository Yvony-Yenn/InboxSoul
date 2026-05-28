"""Style-anchor retrieval for Agent 4.

Given a new incoming email, return the user's past replies whose original
incoming context most resembles the new one. These anchor the agent's voice
without leaking unrelated thread content into the prompt.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.rag.chroma_store import ChromaStore


class StyleRetriever:
    def __init__(self, store: ChromaStore) -> None:
        self.store = store

    def retrieve(
        self,
        incoming_body: str,
        category: str | None = None,
        k: int = 3,
    ) -> list[str]:
        where = {"category": category} if category else None
        hits = self.store.query(text=incoming_body, k=k, where=where)
        return [h["metadata"]["user_reply"] for h in hits if h["metadata"].get("user_reply")]


def seed_from_jsonl(store: ChromaStore, fixture_path: str | Path) -> int:
    """Idempotently load past-reply records into the store. Returns count added.

    Expected JSONL fields per line: id, category, incoming_body, user_reply
    (incoming_subject is optional and ignored at index time).
    """
    existing = store.existing_ids()
    records: list[dict[str, str]] = []
    with Path(fixture_path).open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec["id"] in existing:
                continue
            records.append(rec)

    if not records:
        return 0

    store.add(
        ids=[r["id"] for r in records],
        documents=[r["incoming_body"] for r in records],
        metadatas=[
            {"category": r["category"], "user_reply": r["user_reply"]} for r in records
        ],
    )
    return len(records)