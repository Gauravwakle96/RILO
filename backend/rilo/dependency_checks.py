"""Optional OSV queries for explicitly resolved dependency versions."""

from __future__ import annotations

import json
import re

import httpx

from .engine import bounded_json
from .storage import now


def resolved_dependencies(sources: list[dict]) -> list[dict]:
    packages = []
    for source in sources:
        path, content = source["reference"], source["content"]
        if path.endswith("requirements.txt"):
            for line in content.splitlines():
                match = re.fullmatch(r"\s*([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+\-]+)\s*(?:#.*)?", line)
                if match:
                    packages.append(
                        {
                            "name": match[1],
                            "version": match[2],
                            "ecosystem": "PyPI",
                            "reference": path,
                        }
                    )
        if path.endswith("package-lock.json"):
            try:
                lock = json.loads(content)
                for package_path, item in lock.get("packages", {}).items():
                    if (
                        package_path
                        and isinstance(item, dict)
                        and isinstance(item.get("version"), str)
                        and ("name" not in item or isinstance(item["name"], str))
                    ):
                        packages.append(
                            {
                                "name": item.get(
                                    "name", package_path.rsplit("node_modules/", 1)[-1]
                                ),
                                "version": item["version"],
                                "ecosystem": "npm",
                                "reference": path,
                            }
                        )
            except (ValueError, AttributeError):
                continue
    unique = {(p["ecosystem"], p["name"], p["version"]): p for p in packages}
    return list(unique.values())[:100]


async def check(sources: list[dict]) -> dict:
    packages = resolved_dependencies(sources)
    if not packages:
        return {
            "status": "not_applicable",
            "packages_checked": 0,
            "reason": "No supported exact versions in captured package-lock.json or requirements.txt.",
        }
    async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False) as client:
        result = await bounded_json(
            client,
            "POST",
            "https://api.osv.dev/v1/querybatch",
            json={
                "queries": [
                    {
                        "package": {"name": p["name"], "ecosystem": p["ecosystem"]},
                        "version": p["version"],
                    }
                    for p in packages
                ]
            },
        )
    results = result.get("results")
    if (
        not isinstance(results, list)
        or len(results) != len(packages)
        or any(
            not isinstance(item, dict) or not isinstance(item.get("vulns", []), list)
            for item in results
        )
    ):
        raise ValueError("OSV returned an invalid package-results list.")
    return {
        "status": "completed",
        "provider": "OSV",
        "retrieved_at": now(),
        "packages_checked": len(packages),
        "results": [
            {
                **package,
                "advisories": [
                    {
                        "id": advisory.get("id"),
                        "modified": advisory.get("modified"),
                        "url": "https://osv.dev/vulnerability/" + advisory["id"],
                    }
                    for advisory in result.get("vulns", [])
                    if isinstance(advisory, dict) and isinstance(advisory.get("id"), str)
                ],
            }
            for package, result in zip(packages, results, strict=True)
        ],
        "limitations": [
            "Known advisory matching does not prove runtime exploitability.",
            "Only captured exact versions are queried; at most 100 packages.",
            "Outdated-package checks are not performed.",
        ],
    }
