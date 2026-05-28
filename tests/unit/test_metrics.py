"""Unit tests for evaluation/metrics.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluation.metrics import categorical_accuracy, set_metrics


def test_categorical_perfect_accuracy() -> None:
    s = categorical_accuracy("category", ["work", "work", "spam"], ["work", "work", "spam"])
    assert s.correct == 3
    assert s.total == 3
    assert s.accuracy == 1.0
    assert s.confusions == {}


def test_categorical_partial_accuracy_and_confusions() -> None:
    s = categorical_accuracy(
        "category",
        predictions=["work", "personal", "spam"],
        expected=["work", "work", "promotion"],
    )
    assert s.correct == 1
    assert s.total == 3
    assert abs(s.accuracy - 1 / 3) < 1e-6
    assert s.confusions == {("work", "personal"): 1, ("promotion", "spam"): 1}


def test_categorical_handles_none_prediction() -> None:
    """If pipeline crashed, prediction may be None — should count as a miss."""
    s = categorical_accuracy("category", [None, "work"], ["work", "work"])
    assert s.correct == 1
    assert s.total == 2


def test_set_metrics_perfect_match() -> None:
    s = set_metrics("risk_flags", [{"money", "deadline"}], [{"money", "deadline"}])
    assert s.tp == 2 and s.fp == 0 and s.fn == 0
    assert s.precision == 1.0 and s.recall == 1.0 and s.f1 == 1.0


def test_set_metrics_partial_overlap() -> None:
    s = set_metrics(
        "risk_flags",
        predictions=[{"money", "external_link"}],
        expected=[{"money", "deadline"}],
    )
    assert s.tp == 1  # money in both
    assert s.fp == 1  # external_link predicted but not expected
    assert s.fn == 1  # deadline expected but not predicted
    assert s.precision == 0.5
    assert s.recall == 0.5


def test_set_metrics_missing_prediction_counts_as_all_fn() -> None:
    s = set_metrics("risk_flags", [None], [{"money", "account"}])
    assert s.tp == 0 and s.fp == 0 and s.fn == 2
    assert s.recall == 0.0


def test_set_metrics_aggregates_across_emails() -> None:
    s = set_metrics(
        "risk_flags",
        predictions=[{"money"}, {"deadline"}, set()],
        expected=[{"money"}, {"deadline", "school"}, {"money"}],
    )
    assert s.tp == 2  # money + deadline
    assert s.fp == 0
    assert s.fn == 2  # school + money
    assert s.n_emails == 3