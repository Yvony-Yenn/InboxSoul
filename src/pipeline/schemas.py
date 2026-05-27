"""Canonical Pydantic schemas shared across agents."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Category(StrEnum):
    WORK = "work"
    SCHOOL = "school"
    PERSONAL = "personal"
    FINANCE = "finance"
    PROMOTION = "promotion"
    SYSTEM = "system"
    SPAM = "spam"


class Priority(StrEnum):
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SpamLevel(StrEnum):
    DEFINITE_SPAM = "definite_spam"
    SUSPICIOUS = "suspicious"
    NOT_SPAM = "not_spam"


class ReplyType(StrEnum):
    MUST_REVIEW = "must_review"
    DRAFT_LATER = "draft_later"
    ONE_CLICK = "one_click"
    NO_REPLY = "no_reply"


class RecommendedAction(StrEnum):
    MOVE_TO_JUNK = "move_to_junk"
    ASK_USER_CHECK = "ask_user_check"
    GENERATE_DRAFT = "generate_draft"
    NO_ACTION = "no_action"


class RiskFlag(StrEnum):
    # High-risk flags: Agent 2 must never auto-junk when any of these are present
    MONEY = "money"
    ACCOUNT = "account"
    DEADLINE = "deadline"
    LEGAL = "legal"
    SCHOOL = "school"
    HR = "hr"
    # Lower-risk flags: informational, do not block auto-junk on their own
    EXTERNAL_LINK = "external_link"
    ATTACHMENT = "attachment"
    CREDENTIAL_REQUEST = "credential_request"
    SENSITIVE_PERSONAL_INFO = "sensitive_personal_info"


# Flags that trigger mandatory human review in Agent 2 (CLAUDE.md Critical Safety Rule #2)
HIGH_RISK_FLAGS: frozenset[RiskFlag] = frozenset({
    RiskFlag.MONEY,
    RiskFlag.ACCOUNT,
    RiskFlag.DEADLINE,
    RiskFlag.LEGAL,
    RiskFlag.SCHOOL,
    RiskFlag.HR,
})


class CleanedEmail(BaseModel):
    message_id: str
    sender: str
    subject: str
    body: str
    received_at: datetime


class TriageOutput(BaseModel):
    """Agent 1 output. Contract shared with teammate's Agent 1 implementation."""

    category: Category
    summary: str
    key_points: list[str]
    priority: Priority
    spam_level: SpamLevel
    reply_needed: bool
    reply_type: ReplyType
    # Agent 1 must flag conservatively — if unsure, include the flag rather than omit
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    recommended_action: RecommendedAction
    confidence: float = Field(ge=0.0, le=1.0)


class Draft(BaseModel):
    subject: str
    body: str
    style_references: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class SpamDecision(StrEnum):
    MOVE_TO_JUNK = "move_to_junk"
    REQUIRE_HUMAN_CHECK = "require_human_check"
    PASS = "pass"


class SpamDecisionOutput(BaseModel):
    """Agent 2 output. Pure rule engine — consumes TriageOutput only, never re-reads raw email.

    Decision priority (hard-coded order, safety rules always win):
      1. HIGH_RISK_FLAGS present                  → REQUIRE_HUMAN_CHECK
      2. definite_spam and confidence >= 0.90     → MOVE_TO_JUNK
      3. definite_spam (confidence < 0.90)        → REQUIRE_HUMAN_CHECK
      4. suspicious                               → REQUIRE_HUMAN_CHECK
      5. otherwise                                → PASS
    """

    decision: SpamDecision
    # Human-readable explanation surfaced in Streamlit review UI
    reason: str
    # Which high-risk flags (if any) triggered rule #1 above
    blocked_by_risk_flags: list[RiskFlag] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)