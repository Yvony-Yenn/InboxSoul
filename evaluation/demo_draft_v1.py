"""Agent 4 V1 end-to-end demo: seed corpus -> retrieve style anchors -> draft.

Requires:
  - Ollama running on localhost:11434
  - llama3.1:8b pulled
  - nomic-embed-text pulled

Run from repo root:
    .venv/bin/python evaluation/demo_draft_v1.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.agents.draft import DraftAgent, DraftInput
from src.llm.ollama_client import OllamaClient
from src.pipeline.schemas import (
    Category,
    CleanedEmail,
    Priority,
    RecommendedAction,
    ReplyType,
    SpamLevel,
    TriageOutput,
)
from src.rag.chroma_store import ChromaStore
from src.rag.style_retriever import StyleRetriever, seed_from_jsonl


def make_incoming() -> tuple[CleanedEmail, TriageOutput]:
    email = CleanedEmail(
        message_id="demo-001",
        sender="teammate@acme.com",
        subject="Can you take a look at PR #517 today?",
        body=(
            "Hey — when you have a sec, could you review PR #517? "
            "It touches the same auth path we discussed last week and I'd "
            "like a second pair of eyes before I merge."
        ),
        received_at=datetime.now(),
    )
    triage = TriageOutput(
        category=Category.WORK,
        summary="Teammate asking for a PR review today, touches auth path.",
        key_points=["PR #517", "auth path", "second pair of eyes"],
        priority=Priority.HIGH,
        spam_level=SpamLevel.NOT_SPAM,
        reply_needed=True,
        reply_type=ReplyType.DRAFT_LATER,
        risk_flags=[],
        recommended_action=RecommendedAction.GENERATE_DRAFT,
        confidence=0.95,
    )
    return email, triage


async def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        print(f"[1/4] init chroma store at {td}")
        store = ChromaStore(collection_name="past_replies", persist_dir=td)

        print("[2/4] seed corpus from past_replies.jsonl")
        added = seed_from_jsonl(store, REPO / "tests/fixtures/past_replies.jsonl")
        print(f"      added {added} records (store count = {store.count()})")

        email, triage = make_incoming()
        print("\n[3/4] retrieve style anchors for incoming:")
        print(f"      subject: {email.subject!r}")
        retriever = StyleRetriever(store)
        anchors = retriever.retrieve(email.body, category="work", k=3)
        for i, a in enumerate(anchors, 1):
            print(f"      anchor {i}: {a!r}")

        print("\n[4/4] running DraftAgent with llama3.1:8b ...")
        agent = DraftAgent(llm=OllamaClient())
        draft = await agent.run(
            DraftInput(email=email, triage=triage, style_anchors=anchors)
        )

        print("\n" + "=" * 60)
        print("DRAFT OUTPUT")
        print("=" * 60)
        print(f"Subject: {draft.subject}")
        print(f"\nBody:\n{draft.body}")
        print("=" * 60)
        print(f"style_references recorded: {len(draft.style_references)}")


if __name__ == "__main__":
    asyncio.run(main())