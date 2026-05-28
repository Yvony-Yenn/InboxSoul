"""Agent 3 (reply_policy) unit tests — covers all 7 decision paths."""

from __future__ import annotations

from src.agents.reply_policy import run_reply_policy
from src.pipeline.schemas import (
    Category,
    Priority,
    RecommendedAction,
    ReplyPolicy,
    ReplyType,
    SpamDecision,
    SpamDecisionOutput,
    SpamLevel,
    TriageOutput,
)


def _triage(
    reply_type: ReplyType = ReplyType.DRAFT_LATER, reply_needed: bool = True
) -> TriageOutput:
    return TriageOutput(
        category=Category.WORK,
        summary="s",
        key_points=[],
        priority=Priority.MEDIUM,
        spam_level=SpamLevel.NOT_SPAM,
        reply_needed=reply_needed,
        reply_type=reply_type,
        risk_flags=[],
        recommended_action=RecommendedAction.GENERATE_DRAFT,
        confidence=0.9,
    )


def _spam(decision: SpamDecision = SpamDecision.PASS) -> SpamDecisionOutput:
    return SpamDecisionOutput(decision=decision, reason="", confidence=0.9)


# ---- NO_REPLY paths ---------------------------------------------------------


def test_spam_move_to_junk_means_no_reply() -> None:
    out = run_reply_policy(_triage(), _spam(SpamDecision.MOVE_TO_JUNK))
    assert out.decision == ReplyPolicy.NO_REPLY
    assert "junk" in out.reason.lower()


def test_reply_not_needed_means_no_reply() -> None:
    out = run_reply_policy(_triage(reply_needed=False), _spam())
    assert out.decision == ReplyPolicy.NO_REPLY
    assert "reply_needed" in out.reason


def test_reply_type_no_reply_means_no_reply() -> None:
    out = run_reply_policy(_triage(reply_type=ReplyType.NO_REPLY), _spam())
    assert out.decision == ReplyPolicy.NO_REPLY


# ---- DEFER_TO_USER paths ----------------------------------------------------


def test_spam_require_human_check_defers() -> None:
    out = run_reply_policy(_triage(), _spam(SpamDecision.REQUIRE_HUMAN_CHECK))
    assert out.decision == ReplyPolicy.DEFER_TO_USER
    assert "human review" in out.reason.lower()


def test_must_review_defers() -> None:
    out = run_reply_policy(_triage(reply_type=ReplyType.MUST_REVIEW), _spam())
    assert out.decision == ReplyPolicy.DEFER_TO_USER
    assert "must_review" in out.reason


# ---- DRAFT_NOW paths --------------------------------------------------------


def test_one_click_drafts_now() -> None:
    out = run_reply_policy(_triage(reply_type=ReplyType.ONE_CLICK), _spam())
    assert out.decision == ReplyPolicy.DRAFT_NOW
    assert "one_click" in out.reason


def test_draft_later_drafts_now() -> None:
    out = run_reply_policy(_triage(reply_type=ReplyType.DRAFT_LATER), _spam())
    assert out.decision == ReplyPolicy.DRAFT_NOW


# ---- Pass-throughs -----------------------------------------------------------


def test_confidence_passes_through() -> None:
    triage = _triage()
    triage_with_low_conf = triage.model_copy(update={"confidence": 0.35})
    out = run_reply_policy(triage_with_low_conf, _spam())
    assert out.confidence == 0.35