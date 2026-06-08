"""Minimal dev daemon — runs the REAL pipeline (triage→spam→reply→draft) with
no chromadb/RAG/feedback, so the Chrome extension has a backend on :8000.

Setup:  uv pip install fastapi uvicorn
Run:    uv run uvicorn _dev_daemon:app --port 8000
Delete once the real src/ui/api.py runs.
"""

from __future__ import annotations

import logging
import os
from functools import partial
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from pydantic import BaseModel

from src.agents.draft import DraftAgent
from src.agents.spam_decision import run_spam_decision
from src.agents.triage import run_triage
from src.ingestion.cleaner import clean_message
from src.ingestion.gmail_auth import get_gmail_service
from src.ingestion.gmail_source import GmailSource
from src.ingestion.raw_parser import RawEmail
from src.llm.ollama_client import OllamaClient
from src.pipeline.orchestrator import Orchestrator
from src.pipeline.schemas import ProcessResult
from src.review.executor import GmailExecutor
from src.review.poller import run_once

logging.basicConfig(level=logging.INFO)

_llm = OllamaClient()
_orch = Orchestrator(
    triage_runner=partial(run_triage, llm_client=_llm),
    spam_decider=run_spam_decision,
    draft_agent=DraftAgent(llm=_llm),
)

POLL_INTERVAL_MIN = int(os.getenv("POLL_INTERVAL_MIN", "10"))
_gmail: tuple[GmailSource, GmailExecutor] | None = None


def _gmail_components() -> tuple[GmailSource, GmailExecutor]:
    global _gmail
    if _gmail is None:
        service = get_gmail_service()
        _gmail = (GmailSource(service), GmailExecutor(service))
    return _gmail


async def _poll() -> None:
    source, executor = _gmail_components()
    await run_once(source, _orch, executor)


app = FastAPI(title="InboxSoul dev daemon")


@app.on_event("startup")
async def _start_scheduler() -> None:
    if not Path("token.json").exists():
        logging.getLogger("inboxsoul").warning(
            "token.json not found — run `uv run python -m src.ingestion.gmail_auth` "
            "first. Gmail polling disabled."
        )
        return
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_poll, "interval", minutes=POLL_INTERVAL_MIN)
    scheduler.start()
    logging.getLogger("inboxsoul").info(
        "Gmail polling every %d min (EXECUTOR_DRY_RUN=%s)",
        POLL_INTERVAL_MIN,
        os.getenv("EXECUTOR_DRY_RUN", "true"),
    )


class ProcessEmailRequest(BaseModel):
    message_id: str
    sender: str
    subject: str
    body: str
    body_content_type: str = "text"
    received_at: str


@app.post("/api/process_email", response_model=ProcessResult)
async def process_email(req: ProcessEmailRequest) -> ProcessResult:
    cleaned = clean_message(RawEmail(**req.model_dump()))
    return await _orch.process_cleaned(cleaned)


@app.post("/api/run_now")
async def run_now() -> dict[str, object]:
    source, executor = _gmail_components()
    processed = await run_once(source, _orch, executor)
    return {
        "processed": processed,
        "dry_run": os.getenv("EXECUTOR_DRY_RUN", "true").lower() != "false",
    }