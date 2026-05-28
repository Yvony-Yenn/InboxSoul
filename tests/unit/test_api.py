"""Unit tests for src/ui/api.py — orchestrator + Hermes are mocked via dep override."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.hermes.feedback_store import FeedbackWriter
from src.pipeline.orchestrator import Orchestrator
from src.pipeline.schemas import (
    Category,
    CleanedEmail,
    Draft,
    Priority,
    ProcessResult,
    RecommendedAction,
    ReplyPolicy,
    ReplyPolicyOutput,
    ReplyType,
    RiskFlag,
    SafetyDecision,
    SpamDecision,
    SpamDecisionOutput,
    SpamLevel,
    TriageOutput,
)
from src.ui import api as api_module
from src.ui.api import app, get_feedback_writer, get_orchestrator


def _sample_process_result() -> ProcessResult:
    return ProcessResult(
        cleaned_email=CleanedEmail(
            message_id="m-1",
            sender="x@y.com",
            subject="hi",
            body="body",
            received_at=datetime(2026, 5, 27, 9, 0),
        ),
        triage=TriageOutput(
            category=Category.WORK,
            summary="s",
            key_points=[],
            priority=Priority.MEDIUM,
            spam_level=SpamLevel.NOT_SPAM,
            reply_needed=True,
            reply_type=ReplyType.DRAFT_LATER,
            risk_flags=[],
            recommended_action=RecommendedAction.GENERATE_DRAFT,
            confidence=0.9,
        ),
        safety=SafetyDecision(),
        spam_decision=SpamDecisionOutput(decision=SpamDecision.PASS, reason="ok", confidence=0.9),
        reply_policy=ReplyPolicyOutput(
            decision=ReplyPolicy.DRAFT_NOW, reason="draft", confidence=0.9
        ),
        final_action=RecommendedAction.GENERATE_DRAFT,
        draft=Draft(subject="Re: hi", body="reply"),
    )


@pytest.fixture
def client():
    mock_orch = AsyncMock(spec=Orchestrator)
    mock_orch.process_cleaned = AsyncMock(return_value=_sample_process_result())
    mock_writer = MagicMock(spec=FeedbackWriter)

    api_module._orchestrator = mock_orch
    api_module._feedback_writer = mock_writer
    app.dependency_overrides[get_orchestrator] = lambda: mock_orch
    app.dependency_overrides[get_feedback_writer] = lambda: mock_writer

    with TestClient(app) as c:
        yield c, mock_orch, mock_writer

    app.dependency_overrides.clear()
    api_module._orchestrator = None
    api_module._feedback_writer = None


def _valid_request() -> dict:
    return {
        "message_id": "m-1",
        "sender": "x@y.com",
        "subject": "hi",
        "body": "<p>body</p>",
        "body_content_type": "html",
        "received_at": "2026-05-27T09:00:00+00:00",
    }


def test_health(client) -> None:
    c, _, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_process_email_happy_path(client) -> None:
    c, mock_orch, _ = client
    resp = c.post("/api/process_email", json=_valid_request())
    assert resp.status_code == 200
    body = resp.json()
    assert body["final_action"] == "generate_draft"
    assert body["draft"]["body"] == "reply"
    assert body["reply_policy"]["decision"] == "draft_now"
    mock_orch.process_cleaned.assert_awaited_once()


def test_process_email_missing_field_returns_422(client) -> None:
    c, _, _ = client
    bad = _valid_request()
    del bad["subject"]
    resp = c.post("/api/process_email", json=bad)
    assert resp.status_code == 422


def test_process_email_pipeline_crash_returns_500(client) -> None:
    c, mock_orch, _ = client
    mock_orch.process_cleaned = AsyncMock(side_effect=ValueError("kaboom"))
    resp = c.post("/api/process_email", json=_valid_request())
    assert resp.status_code == 500
    assert "kaboom" in resp.json()["detail"]


def test_feedback_happy_path(client) -> None:
    c, _, mock_writer = client
    payload = {
        "id": "fb-1",
        "incoming_email": {
            "message_id": "m-1",
            "sender": "x@y.com",
            "subject": "hi",
            "body": "body",
            "received_at": "2026-05-27T09:00:00",
        },
        "draft_v0": "v0",
        "final_sent": "final",
        "user_action": "edited_then_sent",
        "created_at": "2026-05-27T10:00:00",
    }
    resp = c.post("/api/feedback", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {"status": "stored", "id": "fb-1"}
    mock_writer.record.assert_called_once()