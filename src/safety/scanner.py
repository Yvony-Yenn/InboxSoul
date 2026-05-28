"""Safety scanner — pipeline's red line. CLAUDE.md mandates 100% test coverage.

Uses HIGH_RISK_FLAGS from src/pipeline/schemas.py (shared with Agent 2). When
the canonical list of high-risk flags changes, change it there — both places
update together.
"""

from __future__ import annotations

from src.pipeline.schemas import (
    HIGH_RISK_FLAGS,
    RecommendedAction,
    RiskFlag,
    SafetyDecision,
    TriageOutput,
)


def scan(triage: TriageOutput) -> SafetyDecision:
    """Return a SafetyDecision. If override_action is set, the orchestrator
    must use it instead of triage.recommended_action."""
    flagged: list[RiskFlag] = sorted(
        set(triage.risk_flags) & HIGH_RISK_FLAGS, key=lambda r: r.value
    )
    if not flagged:
        return SafetyDecision()

    # Red-line rule #2: never auto-junk / auto-delete high-risk flagged emails.
    if triage.recommended_action == RecommendedAction.MOVE_TO_JUNK:
        return SafetyDecision(
            override_action=RecommendedAction.ASK_USER_CHECK,
            reason=(
                f"risk_flags {[f.value for f in flagged]} block auto-junk; "
                "routing to human review"
            ),
        )

    return SafetyDecision()