"""End-to-end orchestrator tests with teammate's REAL Agent 2 + mocked Agent 1/4."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.agents.draft import DraftAgent
from src.agents.spam_decision import run_spam_decision
from src.pipeline.orchestrator import Orchestrator
from src.pipeline.schemas import (
    Category,
    Draft,
    Priority,
    ProcessResult,
    RecommendedAction,
    ReplyPolicy,
    ReplyType,
    RiskFlag,
    SpamDecision,
    SpamLevel,
    TriageOutput,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "raw_emails"


def _triage_out(
    *,
    action: RecommendedAction,
    spam_level: SpamLevel = SpamLevel.NOT_SPAM,
    reply_needed: bool = True,
    reply_type: ReplyType = ReplyType.DRAFT_LATER,
    risk_flags: list[RiskFlag] | None = None,
    confidence: float = 0.95,
) -> TriageOutput:
    return TriageOutput(
        category=Category.WORK,
        summary="s",
        key_points=[],
        priority=Priority.MEDIUM,
        spam_level=spam_level,
        reply_needed=reply_needed,
        reply_type=reply_type,
        risk_flags=risk_flags or [],
        recommended_action=action,
        confidence=confidence,
    )


def _draft() -> Draft:
    return Draft(subject="Re: x", body="ok")


def _make_orchestrator(
    triage_return: TriageOutput, draft_return: Draft | None = None
) -> tuple[Orchestrator, AsyncMock, AsyncMock]:
    triage_runner = AsyncMock(return_value=triage_return)
    draft_agent = AsyncMock(spec=DraftAgent)
    draft_agent.run = AsyncMock(return_value=draft_return or _draft())
    orch = Orchestrator(
        triage_runner=triage_runner,
        spam_decider=run_spam_decision,  # use teammate's real Agent 2
        draft_agent=draft_agent,
    )
    return orch, triage_runner, draft_agent.run


@pytest.fixture
def raw_email() -> bytes:
    return (FIXTURES / "plain.eml").read_bytes()


async def test_happy_path_generates_draft(raw_email: bytes) -> None:
    orch, _, draft_run = _make_orchestrator(
        _triage_out(action=RecommendedAction.GENERATE_DRAFT)
    )
    result = await orch.process_email(raw_email)
    assert isinstance(result, ProcessResult)
    assert result.draft is not None
    assert result.final_action == RecommendedAction.GENERATE_DRAFT
    assert result.safety.override_action is None
    assert result.spam_decision.decision == SpamDecision.PASS
    draft_run.assert_awaited_once()


async def test_safety_overrides_auto_junk_when_money_flag(raw_email: bytes) -> None:
    """Red line: definite_spam + money flag must NOT auto-junk. Both safety AND
    Agent 2 should block — defense in depth."""
    orch, _, draft_run = _make_orchestrator(
        _triage_out(
            action=RecommendedAction.MOVE_TO_JUNK,
            spam_level=SpamLevel.DEFINITE_SPAM,
            risk_flags=[RiskFlag.MONEY],
            reply_needed=False,
            reply_type=ReplyType.NO_REPLY,
        )
    )
    result = await orch.process_email(raw_email)
    assert result.safety.override_action == RecommendedAction.ASK_USER_CHECK
    assert result.spam_decision.decision == SpamDecision.REQUIRE_HUMAN_CHECK
    assert RiskFlag.MONEY in result.spam_decision.blocked_by_risk_flags
    assert result.final_action == RecommendedAction.ASK_USER_CHECK
    assert result.draft is None
    draft_run.assert_not_awaited()


async def test_definite_spam_high_confidence_routes_to_junk(raw_email: bytes) -> None:
    orch, _, draft_run = _make_orchestrator(
        _triage_out(
            action=RecommendedAction.MOVE_TO_JUNK,
            spam_level=SpamLevel.DEFINITE_SPAM,
            risk_flags=[RiskFlag.EXTERNAL_LINK],  # not high-risk
            reply_needed=False,
            reply_type=ReplyType.NO_REPLY,
            confidence=0.95,
        )
    )
    result = await orch.process_email(raw_email)
    assert result.spam_decision.decision == SpamDecision.MOVE_TO_JUNK
    assert result.final_action == RecommendedAction.MOVE_TO_JUNK
    assert result.draft is None
    draft_run.assert_not_awaited()


async def test_definite_spam_low_confidence_routes_to_human(raw_email: bytes) -> None:
    """Agent 2 escalates: definite_spam with confidence < 0.9 needs human check."""
    orch, _, draft_run = _make_orchestrator(
        _triage_out(
            action=RecommendedAction.MOVE_TO_JUNK,
            spam_level=SpamLevel.DEFINITE_SPAM,
            reply_needed=False,
            reply_type=ReplyType.NO_REPLY,
            confidence=0.80,
        )
    )
    result = await orch.process_email(raw_email)
    assert result.spam_decision.decision == SpamDecision.REQUIRE_HUMAN_CHECK
    assert result.final_action == RecommendedAction.ASK_USER_CHECK
    draft_run.assert_not_awaited()


async def test_suspicious_routes_to_human(raw_email: bytes) -> None:
    orch, _, draft_run = _make_orchestrator(
        _triage_out(
            action=RecommendedAction.ASK_USER_CHECK,
            spam_level=SpamLevel.SUSPICIOUS,
            reply_needed=False,
            reply_type=ReplyType.NO_REPLY,
        )
    )
    result = await orch.process_email(raw_email)
    assert result.spam_decision.decision == SpamDecision.REQUIRE_HUMAN_CHECK
    assert result.final_action == RecommendedAction.ASK_USER_CHECK
    draft_run.assert_not_awaited()


async def test_must_review_downgrades_draft_to_ask_user(raw_email: bytes) -> None:
    """Triage said draft but Agent 3 vetoes (MUST_REVIEW). Final downgrades."""
    orch, _, draft_run = _make_orchestrator(
        _triage_out(
            action=RecommendedAction.GENERATE_DRAFT,
            reply_type=ReplyType.MUST_REVIEW,
        )
    )
    result = await orch.process_email(raw_email)
    assert result.draft is None
    assert result.final_action == RecommendedAction.ASK_USER_CHECK
    draft_run.assert_not_awaited()


async def test_no_reply_keeps_no_action(raw_email: bytes) -> None:
    orch, _, draft_run = _make_orchestrator(
        _triage_out(
            action=RecommendedAction.NO_ACTION,
            reply_needed=False,
            reply_type=ReplyType.NO_REPLY,
        )
    )
    result = await orch.process_email(raw_email)
    assert result.draft is None
    assert result.final_action == RecommendedAction.NO_ACTION
    draft_run.assert_not_awaited()


async def test_one_click_generates_draft(raw_email: bytes) -> None:
    orch, _, draft_run = _make_orchestrator(
        _triage_out(
            action=RecommendedAction.GENERATE_DRAFT,
            reply_type=ReplyType.ONE_CLICK,
        )
    )
    result = await orch.process_email(raw_email)
    assert result.draft is not None
    draft_run.assert_awaited_once()


async def test_result_includes_cleaned_email_and_spam_decision(raw_email: bytes) -> None:
    """The plugin needs cleaned_email + spam_decision to render context and reasoning."""
    orch, _, _ = _make_orchestrator(
        _triage_out(
            action=RecommendedAction.NO_ACTION,
            reply_needed=False,
            reply_type=ReplyType.NO_REPLY,
        )
    )
    result = await orch.process_email(raw_email)
    assert result.cleaned_email.sender == "alice@acme.com"
    assert "move standup to 10am" in result.cleaned_email.body
    assert result.spam_decision.reason  # non-empty explanation for UI


async def test_result_carries_reply_policy(raw_email: bytes) -> None:
    """ProcessResult must include Agent 3's structured decision + reason."""
    orch, _, _ = _make_orchestrator(
        _triage_out(action=RecommendedAction.GENERATE_DRAFT, reply_type=ReplyType.ONE_CLICK)
    )
    result = await orch.process_email(raw_email)
    assert result.reply_policy.decision == ReplyPolicy.DRAFT_NOW
    assert result.reply_policy.reason
    assert 0.0 <= result.reply_policy.confidence <= 1.0