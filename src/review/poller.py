"""Poller — one cycle: fetch untriaged inbox mail, run the pipeline, execute the verdict.

Wired into APScheduler by the daemon. Idempotent: the executor marks each message
InboxSoul/Triaged, which GmailSource excludes on the next run.
"""

from __future__ import annotations

import logging

from src.ingestion.base import IngestionSource
from src.pipeline.orchestrator import Orchestrator
from src.review.executor import GmailExecutor

logger = logging.getLogger("inboxsoul.poller")


async def run_once(
    source: IngestionSource,
    orchestrator: Orchestrator,
    executor: GmailExecutor,
    limit: int = 25,
) -> int:
    emails = await source.fetch_unread(limit=limit)
    for email in emails:
        result = await orchestrator.process_cleaned(email)
        await executor.apply(result)
    logger.info("poll cycle done: processed %d email(s)", len(emails))
    return len(emails)