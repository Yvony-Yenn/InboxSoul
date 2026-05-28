"""End-to-end orchestrator demo using ALL agents (1-4) + safety + RAG.

  bytes → raw_parser → cleaner → Agent 1 (Triage, LLM)
                                      ↓
                                  safety scan
                                      ↓
                                  Agent 2 (Spam Decision, rules)
                                      ↓
                                  Agent 3 (Reply Policy, rules)
                                      ↓
                                  Agent 4 (Draft, LLM + RAG anchors)
                                      ↓
                                  ProcessResult

Requires:
  - Ollama running on localhost:11434
  - llama3.1:8b pulled
  - nomic-embed-text pulled

Run from repo root:
    .venv/bin/python evaluation/demo_orchestrator.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from functools import partial
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.agents.draft import DraftAgent
from src.agents.spam_decision import run_spam_decision
from src.agents.triage import run_triage
from src.hermes.feedback_store import COLLECTION_NAME as HERMES_COLL
from src.hermes.retriever import FewShotRetriever
from src.llm.ollama_client import OllamaClient
from src.pipeline.orchestrator import Orchestrator
from src.pipeline.schemas import ProcessResult
from src.rag.chroma_store import ChromaStore
from src.rag.style_retriever import StyleRetriever, seed_from_jsonl

FIXTURES = REPO / "tests/fixtures/raw_emails"
DEMO_EMAILS = ["plain.eml", "html_only.eml", "multipart.eml"]


def _print_result(name: str, result: ProcessResult) -> None:
    t = result.triage
    print("\n" + "═" * 72)
    print(f"INPUT: {name}")
    print("═" * 72)
    print(f"  From:    {result.cleaned_email.sender}")
    print(f"  Subject: {result.cleaned_email.subject}")
    print(f"  Body:    {result.cleaned_email.body[:80]!r}")

    print("\n  ┌─ Agent 1 (Triage) ──────────────────────────────────────────────")
    print(f"  │  category:  {t.category.value}")
    print(f"  │  priority:  {t.priority.value}")
    print(f"  │  spam:      {t.spam_level.value}   (confidence {t.confidence:.2f})")
    print(f"  │  risks:     {[f.value for f in t.risk_flags]}")
    print(f"  │  reply:     needed={t.reply_needed}, type={t.reply_type.value}")
    print(f"  │  suggested: {t.recommended_action.value}")
    print(f"  │  summary:   {t.summary}")

    print("  ├─ Safety scanner ────────────────────────────────────────────────")
    if result.safety.overridden:
        print(f"  │  ⚠️ OVERRIDE → {result.safety.override_action.value}")  # type: ignore[union-attr]
        print(f"  │  reason:     {result.safety.reason}")
    else:
        print("  │  (no override)")

    print("  ├─ Agent 2 (Spam Decision) ───────────────────────────────────────")
    sd = result.spam_decision
    print(f"  │  decision:  {sd.decision.value}")
    print(f"  │  reason:    {sd.reason}")
    if sd.blocked_by_risk_flags:
        print(f"  │  blocked:   {[f.value for f in sd.blocked_by_risk_flags]}")

    print("  ├─ Agent 3 (Reply Policy) ────────────────────────────────────────")
    rp = result.reply_policy
    print(f"  │  decision:  {rp.decision.value}")
    print(f"  │  reason:    {rp.reason}")

    print("  └─ FINAL ACTION ──────────────────────────────────────────────────")
    print(f"     → {result.final_action.value}")

    if result.draft is not None:
        print("\n  📝 DRAFT (Agent 4):")
        print(f"     Subject: {result.draft.subject}")
        print(f"     Body:    {result.draft.body}")
        if result.draft.style_references:
            print(f"     anchors used: {len(result.draft.style_references)}")
    else:
        print("\n  📝 (no draft generated)")


async def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        print("[setup] Initializing Chroma collections + seeding style anchors...")
        style_store = ChromaStore("past_replies", persist_dir=td)
        seed_from_jsonl(style_store, REPO / "tests/fixtures/past_replies.jsonl")
        hermes_store = ChromaStore(HERMES_COLL, persist_dir=td)

        print("[setup] Building orchestrator with all 4 agents...")
        llm = OllamaClient()  # llama3.1:8b shared by Agent 1 and Agent 4
        orch = Orchestrator(
            triage_runner=partial(run_triage, llm_client=llm),
            spam_decider=run_spam_decision,
            draft_agent=DraftAgent(llm=llm),
            style_retriever=StyleRetriever(style_store),
            few_shot_retriever=FewShotRetriever(hermes_store),
        )

        for name in DEMO_EMAILS:
            raw = (FIXTURES / name).read_bytes()
            print(f"\n[running pipeline on {name} ...]")
            try:
                result = await orch.process_email(raw)
                _print_result(name, result)
            except Exception as e:
                print(f"  ⚠️ pipeline failed for {name}: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())