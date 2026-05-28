"""Agent 3 — Reply Policy. Pure rule engine, zero tokens.

Consumes TriageOutput + SpamDecisionOutput. Decision order is hard-coded in
ReplyPolicyOutput's docstring — keep them aligned.
"""

from __future__ import annotations

from src.pipeline.schemas import (
    ReplyPolicy,
    ReplyPolicyOutput,
    ReplyType,
    SpamDecision,
    SpamDecisionOutput,
    TriageOutput,
)


def run_reply_policy(
    triage: TriageOutput, spam: SpamDecisionOutput
) -> ReplyPolicyOutput:
    if spam.decision == SpamDecision.MOVE_TO_JUNK:
        return ReplyPolicyOutput(
            decision=ReplyPolicy.NO_REPLY,
            reason="Routed to junk by Agent 2 — no reply needed.",
            confidence=triage.confidence,
        )

    if spam.decision == SpamDecision.REQUIRE_HUMAN_CHECK:
        return ReplyPolicyOutput(
            decision=ReplyPolicy.DEFER_TO_USER,
            reason="Agent 2 flagged for human review — user decides on reply.",
            confidence=triage.confidence,
        )

    # spam.decision == PASS from here on.

    if not triage.reply_needed:
        return ReplyPolicyOutput(
            decision=ReplyPolicy.NO_REPLY,
            reason="Triage marked reply_needed=false (FYI / no obligation).",
            confidence=triage.confidence,
        )

    if triage.reply_type == ReplyType.NO_REPLY:
        return ReplyPolicyOutput(
            decision=ReplyPolicy.NO_REPLY,
            reason="Reply type is no_reply (newsletter / system notification).",
            confidence=triage.confidence,
        )

    if triage.reply_type == ReplyType.MUST_REVIEW:
        return ReplyPolicyOutput(
            decision=ReplyPolicy.DEFER_TO_USER,
            reason="High-stakes reply (must_review) — user must read first; no pre-draft.",
            confidence=triage.confidence,
        )

    # reply_type in {ONE_CLICK, DRAFT_LATER}
    return ReplyPolicyOutput(
        decision=ReplyPolicy.DRAFT_NOW,
        reason=(
            f"reply_type={triage.reply_type.value} — Agent 4 will produce a draft "
            "for one-click send."
        ),
        confidence=triage.confidence,
    )