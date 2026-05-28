"""Evaluation runner — load golden set, run pipeline, compute metrics, write report.

Run from repo root:
    .venv/bin/python evaluation/run_eval.py

Output:
    evaluation/reports/<timestamp>/report.json   (machine-readable)
    evaluation/reports/<timestamp>/report.md     (human-readable summary)
    evaluation/reports/<timestamp>/per_email.json (full per-email details)
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from evaluation.metrics import categorical_accuracy, set_metrics
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

GOLDEN_SET = REPO / "evaluation/golden_set.jsonl"
REPORTS_DIR = REPO / "evaluation/reports"

# Fields we extract from ProcessResult for comparison
CATEGORICAL_FIELDS = (
    "category",
    "spam_level",
    "reply_type",
    "recommended_action",
    "final_action",
)


def _load_golden_set() -> list[dict[str, Any]]:
    rows = []
    with GOLDEN_SET.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


async def _run_one(orch: Orchestrator, raw_path: Path) -> tuple[ProcessResult | None, str | None]:
    try:
        result = await orch.process_email(raw_path.read_bytes())
        return result, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _extract_predictions(result: ProcessResult | None) -> dict[str, Any]:
    if result is None:
        return {f: None for f in CATEGORICAL_FIELDS} | {"risk_flags": None, "safety_overrides": None}
    return {
        "category": result.triage.category.value,
        "spam_level": result.triage.spam_level.value,
        "reply_needed": result.triage.reply_needed,
        "reply_type": result.triage.reply_type.value,
        "recommended_action": result.triage.recommended_action.value,
        "final_action": result.final_action.value,
        "risk_flags": {f.value for f in result.triage.risk_flags},
        "safety_overrides": result.safety.overridden,
    }


def _build_orchestrator(persist_dir: Path) -> Orchestrator:
    style_store = ChromaStore("past_replies", persist_dir=persist_dir)
    seed_from_jsonl(style_store, REPO / "tests/fixtures/past_replies.jsonl")
    hermes_store = ChromaStore(HERMES_COLL, persist_dir=persist_dir)

    llm = OllamaClient()
    return Orchestrator(
        triage_runner=partial(run_triage, llm_client=llm),
        spam_decider=run_spam_decision,
        draft_agent=DraftAgent(llm=llm),
        style_retriever=StyleRetriever(style_store),
        few_shot_retriever=FewShotRetriever(hermes_store),
    )


async def run() -> dict[str, Any]:
    golden = _load_golden_set()
    per_email: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as td:
        orch = _build_orchestrator(Path(td))
        for row in golden:
            raw_path = REPO / row["raw_email_path"]
            result, error = await _run_one(orch, raw_path)
            preds = _extract_predictions(result)
            per_email.append(
                {
                    "id": row["id"],
                    "notes": row.get("notes", ""),
                    "expected": row["expected"],
                    "predicted": {k: (sorted(v) if isinstance(v, set) else v) for k, v in preds.items()},
                    "error": error,
                }
            )

    # Compute metrics
    field_stats = {}
    for fname in CATEGORICAL_FIELDS:
        preds = [r["predicted"][fname] for r in per_email]
        exps = [r["expected"][fname] for r in per_email]
        field_stats[fname] = categorical_accuracy(fname, preds, exps)

    risk_pred = [set(r["predicted"]["risk_flags"]) if r["predicted"]["risk_flags"] is not None else None for r in per_email]
    risk_exp = [set(r["expected"]["risk_flags"]) for r in per_email]
    risk_stats = set_metrics("risk_flags", risk_pred, risk_exp)

    pipeline_failures = sum(1 for r in per_email if r["error"] is not None)

    return {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "n_emails": len(golden),
        "pipeline_failures": pipeline_failures,
        "field_stats": {
            fname: {
                "accuracy": stats.accuracy,
                "correct": stats.correct,
                "total": stats.total,
                "confusions": {f"{exp}→{pred}": n for (exp, pred), n in stats.confusions.items()},
            }
            for fname, stats in field_stats.items()
        },
        "risk_flag_stats": {
            "precision": risk_stats.precision,
            "recall": risk_stats.recall,
            "f1": risk_stats.f1,
            "tp": risk_stats.tp,
            "fp": risk_stats.fp,
            "fn": risk_stats.fn,
        },
        "per_email": per_email,
    }


def _write_reports(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, default=str))
    (out_dir / "per_email.json").write_text(json.dumps(report["per_email"], indent=2, default=str))
    (out_dir / "report.md").write_text(_render_markdown(report))


def _render_markdown(r: dict[str, Any]) -> str:
    lines = [f"# Eval Report — {r['timestamp']}", ""]
    lines.append(f"- N emails: **{r['n_emails']}**")
    lines.append(f"- Pipeline failures (Agent 1 crash etc.): **{r['pipeline_failures']}**")
    lines.append("")
    lines.append("## Field accuracy")
    lines.append("| Field | Correct | Total | Accuracy |")
    lines.append("|---|---|---|---|")
    for fname, s in r["field_stats"].items():
        lines.append(f"| `{fname}` | {s['correct']} | {s['total']} | **{s['accuracy']:.0%}** |")
    lines.append("")
    rf = r["risk_flag_stats"]
    lines.append("## Risk flags (set precision/recall)")
    lines.append(f"- Precision: **{rf['precision']:.0%}**  ({rf['tp']} TP / {rf['tp'] + rf['fp']} predicted)")
    lines.append(f"- Recall:    **{rf['recall']:.0%}**  ({rf['tp']} TP / {rf['tp'] + rf['fn']} expected)")
    lines.append(f"- F1:        **{rf['f1']:.0%}**")
    lines.append("")
    lines.append("## Confusions")
    for fname, s in r["field_stats"].items():
        if s["confusions"]:
            lines.append(f"### `{fname}`")
            for k, n in s["confusions"].items():
                lines.append(f"- {k} ({n}×)")
    lines.append("")
    lines.append("## Errors")
    for row in r["per_email"]:
        if row["error"]:
            lines.append(f"- **{row['id']}**: {row['error']}")
    return "\n".join(lines)


def _print_top_line(r: dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print(f"EVAL — {r['timestamp']}")
    print("=" * 60)
    print(f"  N emails: {r['n_emails']}")
    print(f"  Pipeline failures: {r['pipeline_failures']}")
    print()
    for fname, s in r["field_stats"].items():
        print(f"  {fname:25} {s['accuracy']:>6.0%}  ({s['correct']}/{s['total']})")
    rf = r["risk_flag_stats"]
    print(f"  risk_flags precision      {rf['precision']:>6.0%}")
    print(f"  risk_flags recall         {rf['recall']:>6.0%}")
    print(f"  risk_flags f1             {rf['f1']:>6.0%}")
    print("=" * 60)


async def main() -> None:
    report = await run()
    ts = report["timestamp"].replace(":", "-").replace(".", "-")
    out_dir = REPORTS_DIR / ts
    _write_reports(report, out_dir)
    _print_top_line(report)
    print(f"\nReports written to: {out_dir.relative_to(REPO)}")


if __name__ == "__main__":
    asyncio.run(main())