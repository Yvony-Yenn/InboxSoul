"""100% coverage of the project's red-line safety rules. Required by CLAUDE.md.

These tests fix the contract the orchestrator depends on; every HIGH_RISK_FLAG
must override MOVE_TO_JUNK, and non-flag emails must pass through untouched.
"""

from __future__ import annotations

import pytest

from src.pipeline.schemas import (
    HIGH_RISK_FLAGS,
    Category,
    Priority,
    RecommendedAction,
    ReplyType,
    RiskFlag,
    SpamLevel,
    TriageOutput,
)
from src.safety.scanner import scan


def _triage(
    *,
    action: RecommendedAction,
    risk_flags: list[RiskFlag],
    spam_level: SpamLevel = SpamLevel.NOT_SPAM,
) -> TriageOutput:
    return TriageOutput(
        category=Category.WORK,
        summary="s",
        key_points=[],
        priority=Priority.LOW,
        spam_level=spam_level,
        reply_needed=False,
        reply_type=ReplyType.NO_REPLY,
        risk_flags=risk_flags,
        recommended_action=action,
        confidence=0.9,
    )


@pytest.mark.parametrize("risk_flag", sorted(HIGH_RISK_FLAGS, key=lambda r: r.value))
def test_every_high_risk_flag_overrides_auto_junk(risk_flag: RiskFlag) -> None:
    """Every flag in HIGH_RISK_FLAGS must individually block move_to_junk."""
    triage = _triage(
        action=RecommendedAction.MOVE_TO_JUNK,
        risk_flags=[risk_flag],
        spam_level=SpamLevel.DEFINITE_SPAM,
    )
    decision = scan(triage)
    assert decision.override_action == RecommendedAction.ASK_USER_CHECK
    assert risk_flag.value in (decision.reason or "")


def test_low_risk_flags_pass_through_junk() -> None:
    triage = _triage(
        action=RecommendedAction.MOVE_TO_JUNK,
        risk_flags=[RiskFlag.EXTERNAL_LINK],
        spam_level=SpamLevel.DEFINITE_SPAM,
    )
    decision = scan(triage)
    assert decision.override_action is None
    assert decision.reason is None


def test_empty_risk_flags_pass_through() -> None:
    triage = _triage(action=RecommendedAction.MOVE_TO_JUNK, risk_flags=[])
    assert scan(triage).override_action is None


def test_high_risk_flag_does_not_override_non_junk_actions() -> None:
    """Risk flags route only matter for auto-junk; other actions are fine."""
    for action in (
        RecommendedAction.GENERATE_DRAFT,
        RecommendedAction.ASK_USER_CHECK,
        RecommendedAction.NO_ACTION,
    ):
        triage = _triage(action=action, risk_flags=[RiskFlag.MONEY, RiskFlag.DEADLINE])
        assert scan(triage).override_action is None


def test_multiple_high_risk_flags_all_listed_in_reason() -> None:
    triage = _triage(
        action=RecommendedAction.MOVE_TO_JUNK,
        risk_flags=[RiskFlag.MONEY, RiskFlag.ACCOUNT, RiskFlag.EXTERNAL_LINK],
    )
    reason = scan(triage).reason or ""
    assert "money" in reason
    assert "account" in reason


def test_high_risk_flags_matches_claude_md() -> None:
    """Tripwire: if anyone narrows the red-line set this test catches it."""
    assert HIGH_RISK_FLAGS == frozenset(
        {
            RiskFlag.MONEY,
            RiskFlag.ACCOUNT,
            RiskFlag.DEADLINE,
            RiskFlag.LEGAL,
            RiskFlag.SCHOOL,
            RiskFlag.HR,
        }
    )