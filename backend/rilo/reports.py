"""Deterministic export of persisted evaluations; no generative report summary."""

from __future__ import annotations

import csv
import io
import json
from html import escape

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def report_data(store, experiment_id: str) -> dict:
    value = store.experiment(experiment_id)
    value["runs"] = [store.run(run["id"]) for run in value["runs"]]
    with store.connection() as connection:
        value["artifacts"] = [
            json.loads(row[0])
            for row in connection.execute(
                "SELECT data FROM workspace_artifacts WHERE experiment_id=? AND kind!='report' ORDER BY rowid",
                (experiment_id,),
            )
        ]
    return value


def lines(data: dict) -> list[tuple[str, str]]:
    manifest = data["manifest"]
    task = manifest.get("workspace", {})
    snapshot = manifest.get("snapshot", {})
    result = [
        ("title", "RILO · Evaluation report"),
        ("body", f"Evaluation: {data['id']}"),
        ("body", f"Created: {data['created_at']} · Status: {data['state']}"),
        ("heading", "Task and conditions"),
        ("body", task.get("prompt", data["name"])),
        (
            "body",
            f"Category: {task.get('category', 'research benchmark')} · Model: {data['spec']['model']}",
        ),
        ("body", "Limits: " + json.dumps(data["spec"]["limits"])),
        (
            "body",
            f"Snapshot: {snapshot.get('id', 'See manifest')} · Hash: {snapshot.get('hash', manifest.get('evidence_hash'))}",
        ),
        ("body", "Input metadata: " + json.dumps(snapshot.get("metadata", {}), ensure_ascii=False)),
        (
            "body",
            "Evaluation rubric: "
            + json.dumps(manifest.get("rubric", {"version": manifest.get("grader_version")})),
        ),
        (
            "body",
            "Execution order: sequential, independent agent histories. Shared captured evidence.",
        ),
    ]
    for run in data["runs"]:
        result.extend(
            [
                ("heading", run["agent_name"]),
                ("body", f"Run: {run['id']} · {run['outcome']}"),
                (
                    "body",
                    f"Latency: {run.get('duration_ms')} ms · Input tokens: {run.get('input_tokens')} · Output tokens: {run.get('output_tokens')} · API cost: {run.get('api_cost_usd')}",
                ),
                (
                    "body",
                    "Null usage or cost means unknown/not applicable; consult provenance in JSON.",
                ),
                ("body", (run.get("output") or {}).get("summary", "No completed response.")),
            ]
        )
        assessment = run.get("assessment") or {}
        if assessment.get("evidence_assessment") == "not_applicable":
            result.append(
                (
                    "body",
                    "Conversation response: no sources supplied; factual accuracy is not verified.",
                )
            )
            for note in assessment.get("observations", []):
                result.append(
                    ("body", f"Unverified response note: {note['title']} — {note['claim']}")
                )
        grading = assessment.get("task_checks", {})
        if grading:
            result.extend(
                [
                    ("heading", "Task checks · Promptfoo " + grading.get("version", "")),
                    (
                        "body",
                        f"Status: {grading.get('status')} · Score: {grading.get('score')} · {grading.get('scope')}",
                    ),
                ]
            )
            for check in grading.get("checks", []):
                result.append(
                    (
                        "body",
                        f"{check['name']}: {'PASS' if check['passed'] else 'FAIL'} · {check['reason']}",
                    )
                )
            if grading.get("reason"):
                result.append(("body", grading["reason"]))
        for finding in assessment.get("findings", []):
            verification = finding["verification"]
            result.extend(
                [
                    ("heading", f"{finding['id']}: {finding['title']} [{finding['severity']}]"),
                    ("body", finding["claim"]),
                    ("body", finding["explanation"]),
                    (
                        "body",
                        f"{verification['state']} · {verification['scope']} · Method: {verification['method']}",
                    ),
                ]
            )
            for citation in verification["citations"]:
                result.extend(
                    [
                        (
                            "body",
                            f"Source: {citation.get('source_reference')} · Lines {citation.get('start_line')}–{citation.get('end_line')} · Page {citation.get('page')} · Valid reference: {citation['valid']}",
                        ),
                        ("quote", citation.get("captured_content") or citation["quote"]),
                        (
                            "body",
                            "Matching method: " + citation.get("matching_method", "exact passage"),
                        ),
                    ]
                )
        result.append(("body", "Metrics: " + json.dumps(assessment.get("metrics", {}))))
        for limitation in assessment.get("limitations", []):
            result.append(("body", "Limitation: " + limitation))
    for artifact in data.get("artifacts", []):
        if artifact.get("kind") == "human_review":
            result.append(("heading", "Human review · separate from automated verification"))
            result.append(("body", json.dumps(artifact["data"], ensure_ascii=False)))
    result.append(("heading", "Comparison and retest"))
    for artifact in data.get("artifacts", []):
        result.append(("body", json.dumps(artifact["data"], ensure_ascii=False)))
    result.append(
        (
            "body",
            "Retest against the same snapshot, prompt, model, budgets and rubric. Review changed conditions before interpreting a difference. Source integrity does not establish claim correctness. Unverified findings need review.",
        )
    )
    return result


def export(data: dict, format: str) -> tuple[bytes, str]:
    if format == "json":
        return json.dumps(data, ensure_ascii=False, indent=2).encode(), "application/json"
    if format == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(
            [
                "evaluation_id",
                "run_id",
                "agent",
                "outcome",
                "finding",
                "claim",
                "verification",
                "sources",
                "latency_ms",
                "input_tokens",
                "output_tokens",
                "task_check_status",
                "task_check_score",
                "task_checks",
            ]
        )

        def safe(value):
            text = str(value if value is not None else "")
            return (
                "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text
            )

        for run in data["runs"]:
            findings = (run.get("assessment") or {}).get("findings", []) or [{}]
            for finding in findings:
                verification = finding.get("verification", {})
                writer.writerow(
                    [
                        safe(v)
                        for v in [
                            data["id"],
                            run["id"],
                            run["agent_name"],
                            run["outcome"],
                            finding.get("title"),
                            finding.get("claim"),
                            verification.get("state"),
                            "; ".join(
                                c.get("source_reference") or ""
                                for c in verification.get("citations", [])
                            ),
                            run.get("duration_ms"),
                            run.get("input_tokens"),
                            run.get("output_tokens"),
                            (run.get("assessment") or {}).get("task_checks", {}).get("status"),
                            (run.get("assessment") or {}).get("task_checks", {}).get("score"),
                            json.dumps(
                                (run.get("assessment") or {})
                                .get("task_checks", {})
                                .get("checks", []),
                                ensure_ascii=False,
                            ),
                        ]
                    ]
                )
        return stream.getvalue().encode("utf-8-sig"), "text/csv"
    if format == "md":
        blocks = []
        for kind, text in lines(data):
            # Escape HTML and Markdown control characters supplied by external content.
            text = escape(text).replace("\\", "\\\\")
            for char in "`*_[]!":
                text = text.replace(char, "\\" + char)
            blocks.append(
                (
                    "# "
                    if kind == "title"
                    else "## "
                    if kind == "heading"
                    else "> "
                    if kind == "quote"
                    else ""
                )
                + text
            )
        return "\n\n".join(blocks).encode(), "text/markdown"
    if format == "pdf":
        from .pdf_fonts import fonts, paragraph_text

        fonts()
        pdf_stream = io.BytesIO()
        styles = getSampleStyleSheet()
        styles["BodyText"].fontSize = 9
        styles["BodyText"].leading = 13
        styles["Heading1"].textColor = colors.HexColor("#315ecd")
        for name in ("BodyText", "Title", "Heading2"):
            styles[name].fontName = "RiloNotoSans"
            styles[name].shaping = True
        story = []
        for kind, text in lines(data):
            style = styles[
                "Title" if kind == "title" else "Heading2" if kind == "heading" else "BodyText"
            ]
            # Bounded paragraphs prevent giant model text from overflowing PDF layout.
            for offset in range(0, max(1, len(text)), 3000):
                story.append(Paragraph(paragraph_text(text[offset : offset + 3000]), style))
                story.append(Spacer(1, 7))
        SimpleDocTemplate(
            pdf_stream,
            title="RILO evaluation " + data["id"],
            author="RILO",
            invariant=1,
            leftMargin=0.7 * inch,
            rightMargin=0.7 * inch,
        ).build(story)
        return pdf_stream.getvalue(), "application/pdf"
    raise ValueError("Choose pdf, md, json or csv.")
