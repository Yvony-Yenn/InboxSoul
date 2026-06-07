"""Triage-only eval — Agent 1 against the golden set, reusing evaluation/metrics.py.
Bypasses the orchestrator/RAG so it needs no chromadb. Gives the real numbers
(category/spam/reply_type/recommended_action accuracy + risk_flag P/R/F1) for the
resume bullet. Run: uv run python _triage_eval.py
"""

import asyncio
import json
from pathlib import Path

from evaluation.metrics import categorical_accuracy, set_metrics
from src.agents.triage import run_triage
from src.ingestion.cleaner import clean_message
from src.ingestion.raw_parser import parse_raw_message
from src.llm.ollama_client import OllamaClient

REPO = Path(__file__).resolve().parent
GOLDEN = REPO / "evaluation/golden_set.jsonl"
CAT_FIELDS = ("category", "spam_level", "reply_type", "recommended_action")


async def main() -> None:
    rows = [json.loads(l) for l in GOLDEN.read_text().splitlines() if l.strip()]
    llm = OllamaClient()

    preds = []
    for r in rows:
        raw = (REPO / r["raw_email_path"]).read_bytes()
        t = await run_triage(clean_message(parse_raw_message(raw)), llm)
        preds.append(
            {
                "category": t.category.value,
                "spam_level": t.spam_level.value,
                "reply_type": t.reply_type.value,
                "recommended_action": t.recommended_action.value,
                "risk_flags": {f.value for f in t.risk_flags},
            }
        )

    print(f"\n{'field':24} acc    correct/total")
    print("-" * 45)
    for f in CAT_FIELDS:
        s = categorical_accuracy(f, [p[f] for p in preds], [r["expected"][f] for r in rows])
        print(f"{f:24} {s.accuracy:5.0%}  {s.correct}/{s.total}")

    rs = set_metrics(
        "risk_flags",
        [p["risk_flags"] for p in preds],
        [set(r["expected"]["risk_flags"]) for r in rows],
    )
    print(
        f"\nrisk_flags  precision {rs.precision:.0%}  recall {rs.recall:.0%}  "
        f"f1 {rs.f1:.0%}  (tp={rs.tp} fp={rs.fp} fn={rs.fn})"
    )


asyncio.run(main())
