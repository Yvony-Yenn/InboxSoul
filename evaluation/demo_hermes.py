"""Hermes Stage 1 end-to-end demo: feedback writes -> few-shot retrieval ->
Agent 4 with BOTH style anchors and few-shot examples.

Requires:
  - Ollama running on localhost:11434
  - llama3.1:8b pulled
  - nomic-embed-text pulled

Run from repo root:
    .venv/bin/python evaluation/demo_hermes.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.agents.draft import DraftAgent, DraftInput
from src.hermes.feedback_store import COLLECTION_NAME as HERMES_COLL, FeedbackWriter
from src.hermes.retriever import FewShotRetriever
from src.hermes.schemas import FeedbackRecord, UserAction
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


def simulated_feedback() -> list[FeedbackRecord]:
    base = datetime(2026, 5, 20, 10, 0)
    cases = [
        (
            "PR review request, auth path",
            "Can you take a look at PR #441? Touches the auth middleware so I want a careful eye.",
            "Will look this afternoon. Drop the diff link in Slack if you want me to prioritize.",
            UserAction.EDITED_THEN_SENT,
        ),
        (
            "Standup time change",
            "Heads up — pushing tomorrow's standup to 10am, hope that's fine.",
            "10am works. I'll move the deploy review back 30 min.",
            UserAction.SENT,
        ),
        (
            "Asking for a quick design review",
            "Got 15 min this week to look at the new dashboard mocks before we ship?",
            "Sure — Thursday afternoon works. Send the Figma link and I'll leave comments inline.",
            UserAction.EDITED_THEN_SENT,
        ),
        (
            "Spammy newsletter pitch",
            "Don't miss our exclusive 50% off Q3 webinar series!",
            "(discarded)",
            UserAction.DISCARDED,
        ),
        (
            "Project status check from PM",
            "Quick check-in — where are we on the export feature for next week's release?",
            "Backend's done; UI is in review. Should be merged Wednesday, give or take a day.",
            UserAction.SENT,
        ),
    ]
    records = []
    for i, (subj, body, final, action) in enumerate(cases):
        records.append(
            FeedbackRecord(
                id=f"fb-{i:03d}",
                incoming_email=CleanedEmail(
                    message_id=f"msg-{i:03d}",
                    sender="teammate@acme.com",
                    subject=subj,
                    body=body,
                    received_at=base + timedelta(days=i),
                ),
                draft_v0="(some earlier AI draft)",
                final_sent=final,
                user_action=action,
                created_at=base + timedelta(days=i, hours=1),
            )
        )
    return records


def make_incoming() -> tuple[CleanedEmail, TriageOutput]:
    email = CleanedEmail(
        message_id="demo-001",
        sender="teammate@acme.com",
        subject="PR #519 — quick look before merge?",
        body=(
            "Hey, mind taking a quick look at PR #519 before I merge tomorrow? "
            "It refactors the auth path and I'd appreciate a second pair of eyes."
        ),
        received_at=datetime.now(),
    )
    triage = TriageOutput(
        category=Category.WORK,
        summary="Teammate asking for PR review on auth refactor before tomorrow's merge.",
        key_points=["PR #519", "auth refactor", "second pair of eyes"],
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
        print(f"[1/5] init two chroma collections at {td}")
        style_store = ChromaStore("past_replies", persist_dir=td)
        hermes_store = ChromaStore(HERMES_COLL, persist_dir=td)

        print("[2/5] seed past_replies (style anchors)")
        added = seed_from_jsonl(style_store, REPO / "tests/fixtures/past_replies.jsonl")
        print(f"      past_replies count = {added}")

        print("[3/5] simulate 5 user review events (mix sent / edited / discarded)")
        writer = FeedbackWriter(hermes_store)
        for fb in simulated_feedback():
            writer.record(fb)
        print(f"      hermes_feedback count = {hermes_store.count()} "
              "(includes 1 discarded, will be filtered at retrieval)")

        email, triage = make_incoming()
        print("\n[4/5] retrieve for incoming:", repr(email.subject))

        style_retriever = StyleRetriever(style_store)
        style_anchors = style_retriever.retrieve(email.body, category="work", k=3)
        print(f"\n  --- style anchors ({len(style_anchors)}) ---")
        for i, a in enumerate(style_anchors, 1):
            print(f"  {i}. {a}")

        few_shot_retriever = FewShotRetriever(hermes_store)
        few_shots = few_shot_retriever.retrieve(email.body, k=3)
        print(f"\n  --- hermes few-shots ({len(few_shots)}) ---")
        for i, ex in enumerate(few_shots, 1):
            print(f"  {i}. incoming: {ex.incoming}")
            print(f"     reply:    {ex.reply}")

        print("\n[5/5] running DraftAgent with both signals injected ...")
        agent = DraftAgent(llm=OllamaClient())
        draft = await agent.run(
            DraftInput(
                email=email,
                triage=triage,
                style_anchors=style_anchors,
                few_shot_examples=few_shots,
            )
        )

        print("\n" + "=" * 60)
        print("DRAFT OUTPUT")
        print("=" * 60)
        print(f"Subject: {draft.subject}")
        print(f"\nBody:\n{draft.body}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())