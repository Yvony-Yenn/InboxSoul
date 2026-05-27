"""Tests for Agent 2 (Spam Decision). Safety-critical — must remain at 100% branch coverage."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.agents.spam_decision import run_spam_decision
from src.pipeline.schemas import (
    Category,
    Priority,
    RecommendedAction,
    ReplyType,
    RiskFlag,
    SpamDecision,
    SpamLevel,
    TriageOutput,
)


def _make_triage(
    *,
    spam_level: SpamLevel = SpamLevel.NOT_SPAM,
    confidence: float = 0.95,
    risk_flags: list[RiskFlag] | None = None,
) -> TriageOutput:
    return TriageOutput(
        category=Category.WORK,
        summary="test",
        key_points=["fact"],
        priority=Priority.MEDIUM,
        spam_level=spam_level,
        reply_needed=False,
        reply_type=ReplyType.NO_REPLY,
        risk_flags=risk_flags or [],
        recommended_action=RecommendedAction.NO_ACTION,
        confidence=confidence,
    )


def test_high_risk_flag_blocks_auto_junk_even_when_definite_spam_high_confidence():
    triage = _make_triage(
        spam_level=SpamLevel.DEFINITE_SPAM,
        confidence=0.99,
        risk_flags=[RiskFlag.MONEY],
    )
    result = run_spam_decision(triage)
    assert result.decision == SpamDecision.REQUIRE_HUMAN_CHECK
    assert result.blocked_by_risk_flags == [RiskFlag.MONEY]
    assert result.confidence == pytest.approx(0.99)


def test_definite_spam_at_threshold_moves_to_junk():
    triage = _make_triage(spam_level=SpamLevel.DEFINITE_SPAM, confidence=0.90)
    result = run_spam_decision(triage)
    assert result.decision == SpamDecision.MOVE_TO_JUNK
    assert result.blocked_by_risk_flags == []


def test_definite_spam_above_threshold_moves_to_junk():
    triage = _make_triage(spam_level=SpamLevel.DEFINITE_SPAM, confidence=0.95)
    result = run_spam_decision(triage)
    assert result.decision == SpamDecision.MOVE_TO_JUNK


def test_definite_spam_below_threshold_requires_human_check():
    triage = _make_triage(spam_level=SpamLevel.DEFINITE_SPAM, confidence=0.80)
    result = run_spam_decision(triage)
    assert result.decision == SpamDecision.REQUIRE_HUMAN_CHECK
    assert result.blocked_by_risk_flags == []


def test_suspicious_requires_human_check():
    triage = _make_triage(spam_level=SpamLevel.SUSPICIOUS, confidence=0.60)
    result = run_spam_decision(triage)
    assert result.decision == SpamDecision.REQUIRE_HUMAN_CHECK


def test_not_spam_passes():
    triage = _make_triage(spam_level=SpamLevel.NOT_SPAM, confidence=0.92)
    result = run_spam_decision(triage)
    assert result.decision == SpamDecision.PASS
    assert result.blocked_by_risk_flags == []


def test_multiple_high_risk_flags_recorded_and_low_risk_excluded():
    triage = _make_triage(
        spam_level=SpamLevel.NOT_SPAM,
        confidence=0.70,
        risk_flags=[
            RiskFlag.MONEY,
            RiskFlag.LEGAL,
            RiskFlag.HR,
            RiskFlag.EXTERNAL_LINK,
        ],
    )
    result = run_spam_decision(triage)
    assert result.decision == SpamDecision.REQUIRE_HUMAN_CHECK
    assert set(result.blocked_by_risk_flags) == {
        RiskFlag.MONEY,
        RiskFlag.LEGAL,
        RiskFlag.HR,
    }
    assert RiskFlag.EXTERNAL_LINK not in result.blocked_by_risk_flags


def test_confidence_is_passed_through():
    triage = _make_triage(spam_level=SpamLevel.NOT_SPAM, confidence=0.42)
    result = run_spam_decision(triage)
    assert result.confidence == pytest.approx(0.42)
