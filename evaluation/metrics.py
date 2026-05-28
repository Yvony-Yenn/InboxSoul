"""Pure metric functions for evaluation. No I/O, fully unit-testable."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass
class FieldStats:
    field_name: str
    correct: int = 0
    total: int = 0
    confusions: dict[tuple[str, str], int] = field(default_factory=dict)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


def categorical_accuracy(
    field_name: str, predictions: Iterable[str | None], expected: Iterable[str]
) -> FieldStats:
    stats = FieldStats(field_name=field_name)
    for pred, exp in zip(predictions, expected):
        stats.total += 1
        if pred == exp:
            stats.correct += 1
        else:
            key = (str(exp), str(pred))
            stats.confusions[key] = stats.confusions.get(key, 0) + 1
    return stats


@dataclass
class SetStats:
    """Set-based precision/recall, e.g. for risk_flags."""

    field_name: str
    tp: int = 0  # in pred AND in expected
    fp: int = 0  # in pred but NOT in expected
    fn: int = 0  # in expected but NOT in pred
    n_emails: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


def set_metrics(
    field_name: str,
    predictions: Iterable[set[str] | None],
    expected: Iterable[set[str]],
) -> SetStats:
    stats = SetStats(field_name=field_name)
    for pred, exp in zip(predictions, expected):
        stats.n_emails += 1
        pred_set: set[str] = pred if pred is not None else set()
        stats.tp += len(pred_set & exp)
        stats.fp += len(pred_set - exp)
        stats.fn += len(exp - pred_set)
    return stats