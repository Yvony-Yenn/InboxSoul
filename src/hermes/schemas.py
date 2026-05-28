"""Hermes feedback schemas — what the review UI emits and what retrieval returns."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from src.pipeline.schemas import CleanedEmail


class UserAction(StrEnum):
    SENT = "sent"
    EDITED_THEN_SENT = "edited_then_sent"
    DISCARDED = "discarded"


class FeedbackRecord(BaseModel):
    """One review event. final_sent is the truth signal: what the user actually sent."""

    id: str
    incoming_email: CleanedEmail
    draft_v0: str
    final_sent: str
    user_action: UserAction
    created_at: datetime


class FewShotExample(BaseModel):
    """A (incoming, final_reply) pair surfaced to Agent 4 as a concrete example."""

    incoming: str
    reply: str