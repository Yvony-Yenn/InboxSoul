"""Mock fixtures for Agent 4 V0 — covers four scenarios:
(a) work, (b) school deadline, (c) casual personal, (d) Chinese-language input.
"""

from __future__ import annotations

from datetime import datetime

from src.pipeline.schemas import (
    Category,
    CleanedEmail,
    Priority,
    RecommendedAction,
    ReplyType,
    SpamLevel,
    TriageOutput,
)


def work_email() -> CleanedEmail:
    return CleanedEmail(
        message_id="msg-001",
        sender="pm@acme.com",
        subject="Q2 roadmap review on Friday 3pm?",
        body=(
            "Hey Maan, can you confirm whether Friday 3pm works for the Q2 "
            "roadmap review? I'd like to lock in the agenda by tomorrow."
        ),
        received_at=datetime(2026, 5, 25, 9, 30),
    )


def work_triage() -> TriageOutput:
    return TriageOutput(
        category=Category.WORK,
        summary="PM asking to confirm Friday 3pm meeting for Q2 roadmap review.",
        key_points=[
            "Friday 3pm proposed",
            "Q2 roadmap review",
            "Need agenda confirmed by tomorrow",
        ],
        priority=Priority.HIGH,
        spam_level=SpamLevel.NOT_SPAM,
        reply_needed=True,
        reply_type=ReplyType.DRAFT_LATER,
        risk_flags=[],
        recommended_action=RecommendedAction.GENERATE_DRAFT,
        confidence=0.95,
    )


def school_email() -> CleanedEmail:
    return CleanedEmail(
        message_id="msg-002",
        sender="cs5100-staff@northeastern.edu",
        subject="Reminder: HW5 due Sunday 11:59pm",
        body=(
            "This is a reminder that Homework 5 is due Sunday at 11:59pm. "
            "Late submissions lose 10% per day. Office hours Thursday 4-6pm."
        ),
        received_at=datetime(2026, 5, 25, 14, 0),
    )


def school_triage() -> TriageOutput:
    return TriageOutput(
        category=Category.SCHOOL,
        summary="HW5 reminder, due Sunday 11:59pm, late penalty 10% per day.",
        key_points=["HW5 due Sunday 11:59pm", "Late = -10%/day", "OH Thursday 4-6pm"],
        priority=Priority.MEDIUM,
        spam_level=SpamLevel.NOT_SPAM,
        reply_needed=False,
        reply_type=ReplyType.NO_REPLY,
        risk_flags=["deadline", "school"],
        recommended_action=RecommendedAction.ASK_USER_CHECK,
        confidence=0.9,
    )


def casual_email() -> CleanedEmail:
    return CleanedEmail(
        message_id="msg-003",
        sender="alex@gmail.com",
        subject="coffee this weekend?",
        body="Hey! Free for coffee Saturday morning? Been a while since we caught up.",
        received_at=datetime(2026, 5, 25, 18, 45),
    )


def casual_triage() -> TriageOutput:
    return TriageOutput(
        category=Category.PERSONAL,
        summary="Friend asking about coffee Saturday morning.",
        key_points=["Coffee invitation", "Saturday morning"],
        priority=Priority.LOW,
        spam_level=SpamLevel.NOT_SPAM,
        reply_needed=True,
        reply_type=ReplyType.ONE_CLICK,
        risk_flags=[],
        recommended_action=RecommendedAction.GENERATE_DRAFT,
        confidence=0.97,
    )


def chinese_email() -> CleanedEmail:
    return CleanedEmail(
        message_id="msg-004",
        sender="laoshi@example.cn",
        subject="关于下周课程安排",
        body="同学你好，下周三的课程改为周五同一时间，请确认能否参加。",
        received_at=datetime(2026, 5, 25, 20, 0),
    )