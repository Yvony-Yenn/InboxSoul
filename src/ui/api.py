"""HTTP API around the daemon. Phase 2 Outlook plugin calls these endpoints.

Run with:
    .venv/bin/uvicorn src.ui.api:app --reload --port 8000

Endpoints:
    GET  /health                — liveness / model version
    POST /api/process_email     — structured email JSON → ProcessResult
    POST /api/feedback          — user review action → Hermes feedback store

Bind to localhost only. The daemon never goes on the network; the plugin runs
in-browser/in-Outlook and calls http://localhost:8000.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from functools import partial
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agents.draft import DraftAgent
from src.agents.spam_decision import run_spam_decision
from src.agents.triage import run_triage
from src.hermes.feedback_store import COLLECTION_NAME as HERMES_COLL, FeedbackWriter
from src.hermes.schemas import FeedbackRecord
from src.ingestion.cleaner import clean_message
from src.ingestion.raw_parser import RawEmail
from src.llm.ollama_client import OllamaClient
from src.pipeline.orchestrator import Orchestrator
from src.pipeline.schemas import ProcessResult
from src.rag.chroma_store import ChromaStore

logger = logging.getLogger(__name__)

# Singletons populated at startup. Tests override via FastAPI dependency_overrides.
_orchestrator: Orchestrator | None = None
_feedback_writer: FeedbackWriter | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _orchestrator, _feedback_writer
    llm = OllamaClient()
    style_store = ChromaStore("past_replies", persist_dir="data/chroma")
    hermes_store = ChromaStore(HERMES_COLL, persist_dir="data/chroma")
    _orchestrator = Orchestrator(
        triage_runner=partial(run_triage, llm_client=llm),
        spam_decider=run_spam_decision,
        draft_agent=DraftAgent(llm=llm),
    )
    _feedback_writer = FeedbackWriter(hermes_store)
    logger.info("daemon ready: llama3.1:8b + Chroma at data/chroma")
    yield


app = FastAPI(title="InboxSoul daemon", version="0.1.0", lifespan=lifespan)

# Outlook Add-in iframes run from outlook.office.com / outlook.live.com; allow
# any origin since the daemon is localhost-only (no public exposure).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def get_orchestrator() -> Orchestrator:
    if _orchestrator is None:
        raise HTTPException(503, "Orchestrator not initialized")
    return _orchestrator


def get_feedback_writer() -> FeedbackWriter:
    if _feedback_writer is None:
        raise HTTPException(503, "FeedbackWriter not initialized")
    return _feedback_writer


class ProcessEmailRequest(BaseModel):
    """Plugin-side payload — already-fetched email from Office.js."""

    message_id: str
    sender: str
    subject: str
    body: str
    body_content_type: str = "text"  # "text" | "html"
    received_at: str  # ISO 8601


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "orchestrator_ready": _orchestrator is not None,
        "feedback_writer_ready": _feedback_writer is not None,
    }


@app.post("/api/process_email", response_model=ProcessResult)
async def process_email(
    req: ProcessEmailRequest,
    orch: Orchestrator = Depends(get_orchestrator),
) -> ProcessResult:
    try:
        raw = RawEmail(**req.model_dump())
        cleaned = clean_message(raw)
        return await orch.process_cleaned(cleaned)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("process_email pipeline failure")
        raise HTTPException(500, f"{type(e).__name__}: {e}") from e


@app.post("/api/feedback")
async def feedback(
    record: FeedbackRecord,
    writer: FeedbackWriter = Depends(get_feedback_writer),
) -> dict[str, str]:
    try:
        writer.record(record)
        return {"status": "stored", "id": record.id}
    except Exception as e:
        logger.exception("feedback write failure")
        raise HTTPException(500, f"{type(e).__name__}: {e}") from e