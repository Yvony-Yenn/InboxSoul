"""Schema-level validators — second-line defense against LLM enum hallucinations."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.pipeline.schemas import RiskFlag, TriageOutput


def _valid_payload(**overrides: object) -> dict:
    base: dict = {
        "category": "work",
        "summary": "x",
        "key_points": ["a"],
        "priority": "medium",
        "spam_level": "not_spam",
        "reply_needed": False,
        "reply_type": "no_reply",
        "risk_flags": [],
        "recommended_action": "no_action",
        "confidence": 0.5,
    }
    base.update(overrides)
    return base


def test_unknown_risk_flag_is_silently_dropped():
    payload = _valid_payload(risk_flags=["money", "bogus_flag", "deadline"])
    out = TriageOutput.model_validate(payload)
    assert out.risk_flags == [RiskFlag.MONEY, RiskFlag.DEADLINE]


def test_all_unknown_risk_flags_yields_empty_list():
    payload = _valid_payload(risk_flags=["foo", "bar", "code"])
    out = TriageOutput.model_validate(payload)
    assert out.risk_flags == []


def test_known_risk_flags_unaffected():
    payload = _valid_payload(risk_flags=["money", "deadline", "legal"])
    out = TriageOutput.model_validate(payload)
    assert out.risk_flags == [RiskFlag.MONEY, RiskFlag.DEADLINE, RiskFlag.LEGAL]


def test_non_string_items_in_risk_flags_dropped():
    payload = _valid_payload(risk_flags=["money", 42, None, {"x": 1}])
    out = TriageOutput.model_validate(payload)
    assert out.risk_flags == [RiskFlag.MONEY]


def test_unknown_category_still_raises():
    payload = _valid_payload(category="bogus_category")
    with pytest.raises(ValidationError):
        TriageOutput.model_validate(payload)


def test_unknown_spam_level_still_raises():
    payload = _valid_payload(spam_level="kinda_spam")
    with pytest.raises(ValidationError):
        TriageOutput.model_validate(payload)


def test_unknown_priority_still_raises():
    payload = _valid_payload(priority="super_urgent")
    with pytest.raises(ValidationError):
        TriageOutput.model_validate(payload)


def test_unknown_reply_type_still_raises():
    payload = _valid_payload(reply_type="maybe_reply")
    with pytest.raises(ValidationError):
        TriageOutput.model_validate(payload)
