"""Deterministic calibration metrics for independently labeled verification judgments."""

from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import Field, model_validator

from .schemas import Identifier, StrictModel

State = Literal[
    "VERIFIED", "PARTIALLY VERIFIED", "UNSUPPORTED", "CONTRADICTED", "NEEDS MANUAL REVIEW"
]


class CalibrationItem(StrictModel):
    id: Identifier
    expected: State
    predicted: State
    reviewer: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1, max_length=1000)


class CalibrationDataset(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    items: list[CalibrationItem] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def unique_items(self):
        if len({item.id for item in self.items}) != len(self.items):
            raise ValueError("Calibration item IDs must be unique.")
        return self


def score(dataset: CalibrationDataset) -> dict:
    states = sorted(
        {item.expected for item in dataset.items} | {item.predicted for item in dataset.items}
    )
    confusion = {expected: {predicted: 0 for predicted in states} for expected in states}
    for item in dataset.items:
        confusion[item.expected][item.predicted] += 1
    per_state = {}
    for state in states:
        tp = confusion[state][state]
        fp = sum(confusion[other][state] for other in states if other != state)
        fn = sum(confusion[state][other] for other in states if other != state)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
        per_state[state] = {
            "support": sum(confusion[state].values()),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    f1_values = [value["f1"] for value in per_state.values() if value["f1"] is not None]
    return {
        "name": dataset.name,
        "version": dataset.version,
        "items": len(dataset.items),
        "accuracy": sum(item.expected == item.predicted for item in dataset.items)
        / len(dataset.items),
        "macro_f1": sum(f1_values) / len(f1_values) if f1_values else None,
        "class_distribution": dict(Counter(item.expected for item in dataset.items)),
        "per_state": per_state,
        "confusion_matrix": confusion,
        "scope": "Agreement with independent labels in this versioned dataset; not universal evaluator accuracy.",
    }
