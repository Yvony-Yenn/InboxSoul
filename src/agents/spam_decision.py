"""Agent 2: Spam Decision. Pure rule engine — no LLM, no I/O, consumes TriageOutput only.

Decision order is fixed by CLAUDE.md Critical Safety Rule #3. Any change here is a
safety-critical change and requires updating the canonical rule list in CLAUDE.md and
the SpamDecisionOutput docstring in src/pipeline/schemas.py to stay consistent.
"""

from __future__ import annotations

from src.pipeline.schemas import (
    HIGH_RISK_FLAGS,
    SpamDecision,
    SpamDecisionOutput,
    SpamLevel,
    TriageOutput,
)

_AUTO_JUNK_CONFIDENCE_THRESHOLD = 0.90


def run_spam_decision(triage: TriageOutput) -> SpamDecisionOutput:
    blocked = [flag for flag in triage.risk_flags if flag in HIGH_RISK_FLAGS]
    if blocked:
        return SpamDecisionOutput(
            decision=SpamDecision.REQUIRE_HUMAN_CHECK,
            reason=f"High-risk flag(s) present: {', '.join(f.value for f in blocked)}.",
            blocked_by_risk_flags=blocked,
            confidence=triage.confidence,
        )

    if triage.spam_level == SpamLevel.DEFINITE_SPAM:
        if triage.confidence >= _AUTO_JUNK_CONFIDENCE_THRESHOLD:
            return SpamDecisionOutput(
                decision=SpamDecision.MOVE_TO_JUNK,
                reason="Definite spam with high confidence — safe to auto-junk.",
                confidence=triage.confidence,
            )
        return SpamDecisionOutput(
            decision=SpamDecision.REQUIRE_HUMAN_CHECK,
            reason=(
                f"Definite spam but confidence {triage.confidence:.2f} is below "
                f"auto-junk threshold {_AUTO_JUNK_CONFIDENCE_THRESHOLD:.2f}."
            ),
            confidence=triage.confidence,
        )

    if triage.spam_level == SpamLevel.SUSPICIOUS:
        return SpamDecisionOutput(
            decision=SpamDecision.REQUIRE_HUMAN_CHECK,
            reason="Suspicious email — human review required before any action.",
            confidence=triage.confidence,
        )

    return SpamDecisionOutput(
        decision=SpamDecision.PASS,
        reason="No safety flags or spam signals — passing to next stage.",
        confidence=triage.confidence,
    )
