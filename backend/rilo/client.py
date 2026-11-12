"""Small local Python SDK for the Rilo execution API."""

from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any

import httpx

from .config import loopback_url


class RiloError(RuntimeError):
    """An API error with a safe user-facing message."""


class RiloClient:
    """Connect to a local Rilo server using its private session key.

    The key is read from disk, never printed or embedded in reports. The SDK
    does not execute arbitrary scripts or connect to non-loopback endpoints.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8018",
        data_dir: Path | str = ".rilo",
        *,
        token: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = loopback_url(base_url)
        if token is None:
            path = Path(data_dir) / "session.key"
            try:
                token = path.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise RiloError("Start the local Rilo server before using its SDK or CLI.") from exc
        if not token:
            raise RiloError("The local server session key is empty. Restart Rilo.")
        self._client = httpx.Client(
            base_url=f"{self.base_url}/api/v1/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def __enter__(self) -> RiloClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        if not re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", path):
            raise RiloError("SDK paths must be relative API routes.")
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise RiloError("The local Rilo server could not be reached.") from exc
        if not response.is_success:
            try:
                body = response.json()
                error = body.get("error", body.get("detail", {}))
                message = error.get("message", "") if isinstance(error, dict) else str(error)
            except (ValueError, AttributeError):
                message = ""
            raise RiloError(message or f"Rilo request failed (HTTP {response.status_code}).")
        try:
            value = response.json()
        except ValueError as exc:
            raise RiloError("The local server returned an invalid JSON response.") from exc
        if not isinstance(value, (dict, list)):
            raise RiloError("The local server returned an invalid API response.")
        return value

    def agents(self) -> list[dict[str, Any]]:
        return self.request("GET", "agents")

    def tasks(self) -> list[dict[str, Any]]:
        return self.request("GET", "tasks")

    def experiments(self) -> list[dict[str, Any]]:
        return self.request("GET", "experiments")

    def history(self, *, kind: str = "experiments", query: str = "", page: int = 1) -> dict:
        return self.request(
            "GET", "workspace/history", params={"kind": kind, "query": query, "page": page}
        )

    def conversation(self, configuration: dict) -> dict:
        return self.request("POST", "workspace/conversations", json=configuration)

    def turn(self, conversation_id: str, task: dict, *, idempotency_key: str | None = None) -> dict:
        self._identifier(conversation_id)
        return self.request(
            "POST",
            f"workspace/conversations/{conversation_id}/turns",
            json=task,
            headers={"Idempotency-Key": idempotency_key} if idempotency_key else {},
        )

    def run_suite(self, suite_id: str, *, case: int = 0) -> dict:
        self._identifier(suite_id)
        return self.request(
            "POST", f"workspace/suites/{suite_id}/run", params={"case": case}, json={}
        )

    def retest(self, experiment_id: str, *, slots: list[dict] | None = None) -> dict:
        self._identifier(experiment_id)
        return self.request(
            "POST",
            f"workspace/evaluations/{experiment_id}/retest",
            json={"slots": slots} if slots else None,
        )

    def run_suite_batch(self, suite_id: str) -> dict:
        self._identifier(suite_id)
        return self.request("POST", f"workspace/suites/{suite_id}/batches", json={})

    def suite_batch(self, batch_id: str) -> dict:
        self._identifier(batch_id)
        return self.request("GET", f"workspace/batches/{batch_id}")

    def run(self, spec: dict[str, Any], *, idempotency_key: str | None = None) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
        return self.request("POST", "experiments", json=spec, headers=headers)

    def experiment(self, experiment_id: str) -> dict[str, Any]:
        self._identifier(experiment_id)
        return self.request("GET", f"experiments/{experiment_id}")

    def wait(
        self, experiment_id: str, *, timeout: float = 900, interval: float = 1
    ) -> dict[str, Any]:
        if (
            not math.isfinite(timeout)
            or not math.isfinite(interval)
            or timeout <= 0
            or interval < 0.1
        ):
            raise ValueError(
                "Use a positive timeout and a polling interval of at least 0.1 seconds."
            )
        deadline = time.monotonic() + timeout
        while True:
            result = self.experiment(experiment_id)
            state = result.get("state")
            if state not in {"queued", "running", "completed", "partial", "cancelled", "failed"}:
                raise RiloError("The local server returned an invalid experiment state.")
            if state not in {"queued", "running"}:
                return result
            if time.monotonic() >= deadline:
                raise RiloError("Waiting timed out; the experiment remains visible in Rilo.")
            time.sleep(min(interval, max(0, deadline - time.monotonic())))

    def cancel(self, experiment_id: str) -> dict[str, Any]:
        self._identifier(experiment_id)
        return self.request("POST", f"experiments/{experiment_id}/cancel")

    def compare(
        self, baseline_id: str, candidate_id: str, *, allow_agent_changes: bool = False
    ) -> dict[str, Any]:
        self._identifier(baseline_id)
        self._identifier(candidate_id)
        payload: dict[str, Any] = {"baseline_id": baseline_id, "candidate_id": candidate_id}
        if allow_agent_changes:
            payload["allow_agent_changes"] = True
        return self.request("POST", "comparisons", json=payload)

    def baseline(self, experiment_id: str, name: str) -> dict[str, Any]:
        self._identifier(experiment_id)
        return self.request(
            "POST", "baselines", json={"experiment_id": experiment_id, "name": name}
        )

    def export(self, experiment_id: str, destination: Path, *, format: str = "json") -> None:
        self._identifier(experiment_id)
        if format not in {"json", "csv"}:
            raise ValueError("Reports support json or csv.")
        try:
            response = self._client.get(
                f"experiments/{experiment_id}/report", params={"format": format}
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RiloError("The report could not be downloaded.") from exc
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(response.content)

    @staticmethod
    def _identifier(value: str) -> None:
        if not value or len(value) > 80 or not all(c.isalnum() or c in "_-" for c in value):
            raise RiloError("Invalid Rilo object identifier.")


def pretty(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)
