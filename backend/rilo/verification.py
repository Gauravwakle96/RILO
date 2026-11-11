"""Independent deterministic evidence checks; integrity is separate from correctness."""

from __future__ import annotations

import re

from .catalog import digest
from .workspace_contracts import WorkspaceOutput


def locate_quote(source: dict, quote: str) -> tuple[int, int, str, str] | None:
    position = source["content"].find(quote)
    if position >= 0:
        start = source["start_line"] + source["content"][:position].count("\n")
        return start, start + quote.count("\n"), quote, "exact passage"
    original, quoted = source["content"].splitlines(), quote.splitlines()
    if len(quoted) < 2:
        return None
    for offset in range(len(original) - len(quoted) + 1):
        block = original[offset : offset + len(quoted)]
        shifts = []
        valid = True
        for actual, supplied in zip(block, quoted, strict=True):
            if not actual.strip() and not supplied.strip():
                continue
            if actual.lstrip(" ") != supplied.lstrip(" "):
                valid = False
                break
            shifts.append(
                len(actual) - len(actual.lstrip(" ")) - (len(supplied) - len(supplied.lstrip(" ")))
            )
        if valid and shifts and len(set(shifts)) == 1:
            return (
                source["start_line"] + offset,
                source["start_line"] + offset + len(block) - 1,
                "\n".join(block),
                "consecutive source lines; common indentation offset",
            )
    return None


def verify(output: WorkspaceOutput, evidence: list[dict]) -> dict:
    sources = {item["id"]: item for item in evidence}
    findings = []
    for index, finding in enumerate(output.findings):
        citations = []
        for citation in finding.citations:
            source = sources.get(citation.source_id)
            reasons = []
            located = locate_quote(source, citation.quote) if source else None
            if source is None:
                reasons.append("Source reference was not supplied to the agent.")
            else:
                located_start = located[0] if located else source["start_line"]
                located_end = located[1] if located else located_start + citation.quote.count("\n")
                start = citation.start_line if citation.start_line is not None else located_start
                end = citation.end_line if citation.end_line is not None else located_end
                if not source["start_line"] <= start <= end <= source["end_line"]:
                    reasons.append("Line range is outside the captured passage.")
                else:
                    if not located or located[0] < start or located[1] > end:
                        reasons.append("Quoted passage does not match the selected source lines.")
                if citation.page is not None and citation.page != source.get("page"):
                    reasons.append("Page reference does not match the captured source.")
            citations.append(
                {
                    **citation.model_dump(),
                    "start_line": start if source else citation.start_line,
                    "end_line": end if source else citation.end_line,
                    "page": source.get("page")
                    if source and citation.page is None
                    else citation.page,
                    "reference_origin": "model-specified range"
                    if citation.start_line is not None
                    else "located exact quote in captured source",
                    "valid": not reasons,
                    "captured_content": located[2] if located else None,
                    "matching_method": located[3] if located else "no match",
                    "reasons": reasons,
                    "evidence_id": digest(citation.model_dump())[:24],
                    "snapshot_id": source.get("snapshot_id") if source else None,
                    "source_reference": source.get("reference") if source else None,
                    "content_hash": source.get("content_hash") if source else None,
                    "retrieved_at": source.get("retrieved_at") if source else None,
                }
            )
        valid = [c for c in citations if c["valid"]]
        # Only a verbatim claim can be deterministically grounded by text matching.
        # It is verified as source content, not as an external-world conclusion.
        direct = valid and any(finding.claim == c["quote"] for c in valid)
        status = (
            "VERIFIED"
            if direct and len(valid) == len(citations)
            else "PARTIALLY VERIFIED"
            if valid
            else "UNSUPPORTED"
        )
        findings.append(
            {
                **finding.model_dump(),
                "id": f"finding_{index + 1}",
                "verification": {
                    "state": status,
                    "method": "snapshot_reference_and_exact_passage",
                    "scope": "Source quotation only"
                    if direct
                    else "Reference integrity only; interpretation needs review",
                    "claim_correctness": "source_quote" if direct else "NEEDS MANUAL REVIEW",
                    "citations": citations,
                },
            }
        )
    citation_count = sum(len(f["verification"]["citations"]) for f in findings)
    valid_count = sum(c["valid"] for f in findings for c in f["verification"]["citations"])
    return {
        "status": "inconclusive",
        "checks": [
            {
                "name": "Structured response",
                "passed": True,
                "evidence": "Output matched the declared schema.",
            },
            {
                "name": "Citation validity",
                "passed": valid_count == citation_count if citation_count else None,
                "evidence": f"{valid_count}/{citation_count} citations match captured references.",
            },
        ],
        "findings": findings,
        "metrics": {
            "citation_validity": valid_count / citation_count if citation_count else None,
            "evidence_coverage": sum(bool(f["citations"]) for f in findings) / len(findings)
            if findings
            else None,
            "precision": None,
            "recall": None,
            "f1": None,
            "accuracy": None,
        },
        "rubric_version": "workspace-evidence-v1",
        "limitations": [
            "No ground-truth labels: accuracy, precision, recall and F1 are undefined.",
            "Valid references do not prove an interpretation. Free-text summary is not fully verified.",
            "Subjective quality and instruction adherence need independent review.",
        ],
    }


def compare_findings(runs: list[dict]) -> list[dict]:
    if len(runs) != 2:
        return []
    first = runs[0].get("assessment", {}).get("findings", [])
    second = runs[1].get("assessment", {}).get("findings", [])
    matches = []
    for a in first:
        for b in second:
            shared = {c["source_id"] for c in a["citations"]} & {
                c["source_id"] for c in b["citations"]
            }
            words_a = set(re.findall(r"\w+", a["title"].lower()))
            words_b = set(re.findall(r"\w+", b["title"].lower()))
            similarity = len(words_a & words_b) / max(1, len(words_a | words_b))
            if shared and similarity >= 0.4:
                matches.append(
                    {
                        "agent_a": runs[0]["agent_id"],
                        "agent_b": runs[1]["agent_id"],
                        "finding_a": a["id"],
                        "finding_b": b["id"],
                        "relationship": "same claim"
                        if a["claim"] == b["claim"]
                        else "potential disagreement",
                        "outcome": "Inconclusive",
                        "method": "shared_source_and_title_overlap",
                        "explanation": "Related findings share source references. Different wording alone does not establish a contradiction or a winner.",
                    }
                )
    return matches
