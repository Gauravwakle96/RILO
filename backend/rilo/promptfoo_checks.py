"""Bounded adapter to Promptfoo; output generation and evidence checks stay in Rilo."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path

from .task_checks import TaskCheck, validate_checks

VERSION = "0.125.1"
RUNTIME = Path(__file__).resolve().parent / "promptfoo_runtime"
SCOPE = "Explicit task checks only; not a measurement of overall factual accuracy."


def availability() -> dict:
    package = RUNTIME / "node_modules" / "promptfoo" / "package.json"
    try:
        installed = json.loads(package.read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        installed = None
    ready = bool(shutil.which("node")) and installed == VERSION
    return {
        "available": ready,
        "engine": "promptfoo",
        "version": installed,
        "required_version": VERSION,
        "detail": "Pinned assertion package is installed; execution is checked when grading."
        if ready
        else "Install Node >=22.22.0, then run npm ci --prefix backend/rilo/promptfoo_runtime.",
    }


async def _grade_promptfoo(output: dict, checks: list[dict], timeout: float = 30) -> dict:
    checked = validate_checks([TaskCheck.model_validate(check) for check in checks])
    base = {"engine": "promptfoo", "version": VERSION, "scope": SCOPE}
    if not checked:
        return {**base, "status": "ungraded", "score": None, "checks": []}
    ready = availability()
    if not ready["available"]:
        return {**base, "status": "error", "score": None, "checks": [], "reason": ready["detail"]}
    payload = json.dumps(
        {"output": output, "checks": [check.model_dump() for check in checked]}, ensure_ascii=False
    ).encode()
    if len(payload) > 250_000:
        return {
            **base,
            "status": "error",
            "score": None,
            "checks": [],
            "reason": "Stored response exceeds the grading input limit.",
        }
    # Deliberately do not inherit API credentials, NODE_OPTIONS or provider settings.
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}
    }
    env.update(
        {
            key: "true"
            for key in (
                "PROMPTFOO_DISABLE_TELEMETRY",
                "PROMPTFOO_DISABLE_SHARING",
                "PROMPTFOO_DISABLE_UPDATE",
                "PROMPTFOO_DISABLE_REMOTE_GENERATION",
                "PROMPTFOO_DISABLE_TEMPLATE_ENV_VARS",
                "PROMPTFOO_DISABLE_TEMPLATING",
                "PROMPTFOO_DISABLE_ERROR_LOG",
                "PROMPTFOO_DISABLE_DEBUG_LOG",
            )
        }
    )
    env.update(
        PROMPTFOO_CACHE_ENABLED="false", PROMPTFOO_ASSERTIONS_MAX_CONCURRENCY="1", LOG_LEVEL="error"
    )
    try:
        with tempfile.TemporaryDirectory(prefix="rilo-grader-") as temporary:
            env["PROMPTFOO_CONFIG_DIR"] = temporary
            process = await asyncio.create_subprocess_exec(
                shutil.which("node") or "node",
                "--max-old-space-size=384",
                "--permission",
                f"--allow-fs-read={RUNTIME}",
                f"--allow-fs-read={temporary}",
                f"--allow-fs-write={temporary}",
                str(RUNTIME / "grade.mjs"),
                cwd=temporary,
                env=env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                raw, _ = await asyncio.wait_for(process.communicate(payload), timeout=timeout)
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
            if process.returncode or len(raw) > 100_000:
                raise ValueError("Grading process failed")
            result = json.loads(raw)
            if (
                not isinstance(result, dict)
                or result.get("version") != VERSION
                or not isinstance(result.get("checks"), list)
                or len(result["checks"]) != len(checked)
            ):
                raise ValueError("Grader result does not match the requested checks")
            rows = []
            for spec, row in zip(checked, result["checks"], strict=True):
                if (
                    not isinstance(row, dict)
                    or row["id"] != spec.id
                    or type(row["passed"]) is not bool
                    or type(row["score"]) not in (int, float)
                    or row["score"] != int(row["passed"])
                    or not isinstance(row["reason"], str)
                ):
                    raise ValueError("Invalid assertion result")
                rows.append({**spec.model_dump(), **row})
            passed = sum(row["passed"] for row in rows)
            return {
                **base,
                "status": "pass" if passed == len(rows) else "fail",
                "score": passed / len(rows),
                "passed": passed,
                "total": len(rows),
                "checks": rows,
            }
    except TimeoutError:
        reason = "Promptfoo grading timed out. The original agent response is preserved; retest to try again."
    except (OSError, ValueError, KeyError, TypeError):
        reason = "Promptfoo grading failed. The original agent response is preserved; check the pinned runtime installation."
    return {**base, "status": "error", "score": None, "checks": [], "reason": reason}


async def grade_output(
    output: dict, checks: list[dict], timeout: float = 30, assessment: dict | None = None
) -> dict:
    checked = validate_checks([TaskCheck.model_validate(check) for check in checks])
    native = {"json-field-equals", "max-length", "citations-valid", "has-findings"}
    external = [check.model_dump() for check in checked if check.type not in native]
    result = await _grade_promptfoo(output, external, timeout)
    if result["status"] == "error":
        return result
    rows = [{**row, "method": "Promptfoo " + VERSION} for row in result["checks"]]
    for check in checked:
        if check.type not in native:
            continue
        target = output.get("summary", "") if check.target == "summary" else json.dumps(output)
        passed = False
        reason = "Requirement not met."
        if check.type == "max-length":
            passed = len(target) <= int(check.value or "0")
            reason = f"Observed {len(target)} characters; maximum {check.value}."
        elif check.type == "has-findings":
            passed = bool(output.get("findings"))
            reason = "Structured findings present." if passed else "No structured findings."
        elif check.type == "citations-valid":
            findings = (assessment or {}).get("findings", [])
            citations = [
                citation
                for finding in findings
                for citation in finding.get("verification", {}).get("citations", [])
            ]
            passed = (
                bool(findings)
                and all(finding.get("verification", {}).get("citations") for finding in findings)
                and bool(citations)
                and all(citation.get("valid") for citation in citations)
            )
            reason = (
                "Every finding has matched captured references; claim correctness is separate."
                if passed
                else "Missing or invalid captured references."
            )
        elif check.type == "json-field-equals":
            rule = json.loads(check.value or "{}")
            try:
                value = json.loads(target) if check.target == "summary" else output
                for key in rule["path"].split("."):
                    value = value[int(key)] if isinstance(value, list) else value[key]
                passed = type(value) is type(rule["value"]) and value == rule["value"]
                reason = (
                    "Selected field matches the expected value."
                    if passed
                    else "Selected field differs from the expected value."
                )
            except (ValueError, KeyError, IndexError, TypeError):
                reason = "JSON or requested field is missing."
        rows.append(
            {
                **check.model_dump(),
                "passed": bool(passed),
                "score": int(bool(passed)),
                "reason": reason,
                "method": "Rilo deterministic check",
            }
        )
    if not checked:
        return result
    rows.sort(
        key=lambda row: next(index for index, check in enumerate(checked) if check.id == row["id"])
    )
    passed_count = sum(row["passed"] for row in rows)
    return {
        **result,
        "engine": "promptfoo+rilo" if native & {check.type for check in checked} else "promptfoo",
        "checks": rows,
        "passed": passed_count,
        "total": len(rows),
        "score": passed_count / len(rows),
        "status": "pass" if passed_count == len(rows) else "fail",
    }


def compare_runs(runs: list[dict]) -> dict:
    """A scoped result, never a quality winner inferred from execution speed alone."""
    rows = []
    for run in runs:
        grading = (run.get("assessment") or {}).get("task_checks", {})
        rows.append(
            {
                "run_id": run["id"],
                "agent_id": run["agent_id"],
                "agent_name": run["agent_name"],
                "outcome": run["outcome"],
                "status": grading.get("status", "ungraded"),
                "score": grading.get("score"),
                "passed": grading.get("passed"),
                "total": grading.get("total"),
                "duration_ms": run.get("duration_ms"),
                "reason": grading.get("reason"),
            }
        )
    result: dict = {
        "method": "promptfoo-explicit-checks-v1",
        "scope": SCOPE,
        "agents": rows,
        "winner": None,
        "verdict": "inconclusive",
    }
    signatures = {
        json.dumps(
            [
                {key: check.get(key) for key in ("id", "type", "target", "value")}
                for check in (run.get("assessment") or {}).get("task_checks", {}).get("checks", [])
            ],
            sort_keys=True,
        )
        for run in runs
    }
    if any(run["outcome"] != "completed" for run in runs):
        result["explanation"] = (
            "At least one agent did not complete. Compare recorded failures; there is no complete quality comparison."
        )
    elif any(row["status"] == "error" for row in rows):
        result["explanation"] = (
            "An evaluator failed. Agent answers are preserved, but the comparison could not be graded."
        )
    elif any(row["score"] is None for row in rows):
        result["verdict"] = "ungraded"
        result["explanation"] = (
            "No success checks were defined. Compare answers, evidence and usage; accuracy and a winner remain undetermined. Add explicit checks to the next task."
        )
    else:
        if len(signatures) != 1:
            result["explanation"] = (
                "The agents were graded against different checks. Rerun with identical rules before comparing scores."
            )
            return result
        groups: dict[str, list[dict]] = {}
        for row in rows:
            groups.setdefault(row["agent_id"], []).append(row)
        if len(groups) != 2 or len({len(group) for group in groups.values()}) != 1:
            result["explanation"] = (
                "Comparison requires equal completed trials from two agents. Individual check results are available."
            )
            return result
        means = {
            agent: sum(row["score"] for row in group) / len(group)
            for agent, group in groups.items()
        }
        if all(row["status"] == "fail" for row in rows):
            result["verdict"] = "neither_met_checks"
            result["explanation"] = (
                "Neither agent met all the declared checks. Inspect the failed requirements and source coverage; "
                "literal text checks do not measure factual accuracy and do not correct spelling or word order."
            )
        elif len(set(means.values())) == 1:
            result["verdict"] = "tie"
            result["explanation"] = (
                "Both agents achieved the same explicit check score. Neither is a quality winner on these checks; inspect evidence and latency separately."
            )
        else:
            winner = max(means, key=lambda key: means[key])
            result.update(winner=winner, verdict="checks_leader")
            result["explanation"] = (
                f"{groups[winner][0]['agent_name']} passed a greater share of the declared checks under these conditions. This is a task-check result, not proof of general superiority."
            )
        result["mean_scores"] = means
    return result
