"""Versioned evaluation rubrics, labeled metrics and explicit comparison limits."""

from __future__ import annotations

import math

from pydantic import Field, model_validator

from .schemas import Identifier, StrictModel
from .task_checks import TaskCheck, validate_checks

REPOSITORY_RUBRIC = {
    "version": "repository-v1",
    "weights": {
        "finding_accuracy": 25,
        "evidence_correctness": 20,
        "issue_coverage": 15,
        "task_completion": 15,
        "technical_depth": 10,
        "instruction_adherence": 10,
        "execution_efficiency": 5,
    },
    "policy": "No aggregate score until all weighted criteria have valid independent measurements.",
}


class GroundTruth(StrictModel):
    label_id: Identifier
    reference: str = Field(min_length=1, max_length=300)
    expected_quote: str = Field(min_length=1, max_length=1500)


class SuiteCreate(StrictModel):
    additional_experiment_ids: list[Identifier] = Field(default_factory=list, max_length=9)
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    source_experiment_id: Identifier
    labels: list[GroundTruth] = Field(default_factory=list, max_length=100)
    repetitions: int = Field(default=3, ge=1, le=5)
    checks: list[TaskCheck] | None = Field(default=None, max_length=12)

    @model_validator(mode="after")
    def unique_labels(self):
        validate_checks(self.checks or [])
        if self.source_experiment_id in self.additional_experiment_ids or len(
            set(self.additional_experiment_ids)
        ) != len(self.additional_experiment_ids):
            raise ValueError("Each suite case must reference a distinct evaluation.")
        if len({label.label_id for label in self.labels}) != len(self.labels):
            raise ValueError("Ground-truth label IDs must be unique.")
        if len({(label.reference, label.expected_quote) for label in self.labels}) != len(
            self.labels
        ):
            raise ValueError("Ground-truth quotation labels must be unique.")
        return self


class RegressionCreate(StrictModel):
    baseline_id: Identifier
    candidate_id: Identifier
    allow_agent_changes: bool = False
    allow_input_changes: bool = False


def precision_recall(tp: int, fp: int, fn: int) -> dict:
    if any(type(value) is not int or value < 0 for value in (tp, fp, fn)):
        raise ValueError("Confusion counts must be nonnegative integers.")
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def wilson(success: int, total: int) -> list[float] | None:
    if type(success) is not int or type(total) is not int or not 0 <= success <= total:
        raise ValueError("Successes and trials must be valid nonnegative integers.")
    if total < 5:
        return None
    z = 1.96
    rate = success / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return [max(0, center - margin), min(1, center + margin)]


def compare_workspace(baseline: dict, candidate: dict, spec: RegressionCreate) -> dict:
    if not all(value["manifest"].get("workspace") for value in (baseline, candidate)):
        raise ValueError(
            "Select two workspace evaluations. Research benchmarks use Compare & baselines."
        )
    mismatches: list[str] = []
    changes: list[str] = []
    for field in ("model", "limits", "agent_ids", "repetitions", "mode", "engine"):
        if baseline["spec"][field] != candidate["spec"][field]:
            (changes if field == "model" and spec.allow_agent_changes else mismatches).append(field)
    for field in (
        "workspace_runtime_hash",
        "grader_version",
        "evidence_hash",
        "task_hash",
        "agent_hash",
    ):
        if baseline["manifest"].get(field) != candidate["manifest"].get(field):
            allowed = (
                spec.allow_input_changes
                if field == "evidence_hash"
                else spec.allow_agent_changes
                if field == "agent_hash"
                else False
            )
            (changes if allowed else mismatches).append(field)
    for field in ("category", "histories", "search_provider", "checks", "semantic_review"):
        if baseline["manifest"].get("workspace", {}).get(field) != candidate["manifest"].get(
            "workspace", {}
        ).get(field):
            mismatches.append(field)
    for field in ("slots", "execution_agents"):
        if baseline["manifest"]["workspace"].get(field) != candidate["manifest"]["workspace"].get(
            field
        ):
            (changes if spec.allow_agent_changes else mismatches).append(field)
    for field in ("suite_id", "suite_version", "suite_case", "ground_truth"):
        if baseline["manifest"]["workspace"].get(field) != candidate["manifest"]["workspace"].get(
            field
        ):
            mismatches.append(field)
    differences = []
    for agent_id in baseline["spec"]["agent_ids"]:
        old = [r for r in baseline["runs"] if r["agent_id"] == agent_id]
        new = [r for r in candidate["runs"] if r["agent_id"] == agent_id]

        def findings(runs):
            return {
                f["title"] + " | " + f["claim"]: f
                for r in runs
                for f in (r.get("assessment") or {}).get("findings", [])
            }

        first, second = findings(old), findings(new)

        def mean(runs, field):
            values = [r.get(field) for r in runs]
            return (
                sum(values) / len(values) if values and all(v is not None for v in values) else None
            )

        old_latency, new_latency = mean(old, "duration_ms"), mean(new, "duration_ms")
        old_tokens, new_tokens = mean(old, "output_tokens"), mean(new, "output_tokens")

        def label_mean(runs):
            values = [(r.get("assessment") or {}).get("label_metrics", {}).get("f1") for r in runs]
            return (
                sum(values) / len(values) if values and all(v is not None for v in values) else None
            )

        old_score, new_score = label_mean(old), label_mean(new)

        def check_mean(runs):
            values = [(r.get("assessment") or {}).get("task_checks", {}).get("score") for r in runs]
            return (
                sum(values) / len(values)
                if values and all(value is not None for value in values)
                else None
            )

        old_checks, new_checks = check_mean(old), check_mean(new)

        def failed_checks(runs):
            return sorted(
                {
                    check["name"]
                    for run in runs
                    for check in (run.get("assessment") or {})
                    .get("task_checks", {})
                    .get("checks", [])
                    if not check["passed"]
                }
            )

        def trial_summary(runs):
            successes = sum(r.get("outcome") == "completed" for r in runs)
            return {
                "trials": len(runs),
                "completed": successes,
                "completion_interval_95": wilson(successes, len(runs)),
                "interval_method": "Wilson binomial, >=5 trials; exploratory, no significance claim",
            }

        differences.append(
            {
                "agent_id": agent_id,
                "new_findings": sorted(second.keys() - first.keys()),
                "no_longer_reported": sorted(first.keys() - second.keys()),
                "persistent_findings": sorted(first.keys() & second.keys()),
                "latency_ms_delta": new_latency - old_latency
                if new_latency is not None and old_latency is not None
                else None,
                "output_tokens_delta": new_tokens - old_tokens
                if new_tokens is not None and old_tokens is not None
                else None,
                "baseline_quote_f1": old_score,
                "candidate_quote_f1": new_score,
                "baseline_check_score": old_checks,
                "candidate_check_score": new_checks,
                "check_score_delta": new_checks - old_checks
                if old_checks is not None and new_checks is not None
                else None,
                "newly_failed_checks": sorted(set(failed_checks(new)) - set(failed_checks(old))),
                "now_passing_checks": sorted(set(failed_checks(old)) - set(failed_checks(new)))
                if new_checks is not None
                else [],
                "score_delta": new_score - old_score
                if old_score is not None and new_score is not None
                else None,
                "score_scope": "Labeled source quotation retrieval only; not security accuracy",
                "baseline_trials": trial_summary(old),
                "candidate_trials": trial_summary(new),
            }
        )
    measured = [delta["score_delta"] for delta in differences]
    labeled = measured and all(value is not None for value in measured) and not mismatches
    check_deltas = [delta["check_score_delta"] for delta in differences]
    checkable = (
        bool(check_deltas) and all(value is not None for value in check_deltas) and not mismatches
    )
    return {
        "compatible": not mismatches,
        "mismatches": mismatches,
        "declared_changes": changes,
        "agent_deltas": differences,
        "gate": (
            "regression"
            if any(value < 0 for value in measured if value is not None)
            or any(value < 0 for value in check_deltas if value is not None)
            else "no_observed_regression"
        )
        if labeled or checkable
        else "inconclusive",
        "gate_scope": "Declared task checks and/or expected source quotation retrieval; not general accuracy",
        "limitations": [
            "Finding changes do not prove an issue was fixed or introduced.",
            "Without validated outcome labels, there is no objective accuracy regression score.",
            "Single or small repeated samples do not establish statistical significance.",
        ],
    }
