import copy

import pytest
from rilo.catalog import SOURCES, TASKS
from rilo.evaluation import grade
from rilo.schemas import AgentOutput, Fact


def briefing(first_fact: str) -> AgentOutput:
    return AgentOutput(
        summary="Aurora Labs briefing.",
        facts=[
            {"text": first_fact, "source_ids": ["aurora_launch"]},
            {"text": SOURCES[1]["claims"][0], "source_ids": ["aurora_hire"]},
        ],
    )


@pytest.mark.parametrize("include_both", [False, True])
def test_v2_accepts_required_statement_with_additional_supported_sentence(include_both):
    text = " ".join(SOURCES[0]["claims"]) if include_both else SOURCES[0]["claims"][0]
    result = grade(TASKS[0], briefing(text), SOURCES, "controlled", False, "normal")
    assert result["status"] == "pass"
    assert next(
        check for check in result["checks"] if check["name"] == "Required referenced facts"
    )["passed"]


@pytest.mark.parametrize(
    "text",
    [
        "Aurora Labs did not launch Beacon on October 14, 2026.",
        SOURCES[0]["claims"][0] + " Aurora Labs raised ten million dollars.",
        "It is false that " + SOURCES[0]["claims"][0],
    ],
)
def test_v2_does_not_accept_negation_or_unsupported_appended_content(text):
    result = grade(TASKS[0], briefing(text), SOURCES, "controlled", False, "normal")
    assert result["status"] == "fail"
    assert not next(
        check for check in result["checks"] if check["name"] == "Factual statements supported"
    )["passed"]


def test_v2_required_passage_must_have_full_token_boundaries():
    sources = copy.deepcopy(SOURCES)
    fake_claim = "X" + SOURCES[0]["claims"][0]
    sources[0]["content"] = fake_claim
    result = grade(TASKS[0], briefing(fake_claim), sources, "controlled", False, "normal")
    assert not next(
        check for check in result["checks"] if check["name"] == "Required referenced facts"
    )["passed"]


def test_v2_preserves_entity_and_date_checks_even_with_reference_coverage():
    output = briefing(" ".join(SOURCES[0]["claims"]))
    output.facts.append(Fact(text=SOURCES[3]["claims"][0], source_ids=["aurora_energy"]))
    result = grade(TASKS[0], output, SOURCES, "controlled", False, "normal")
    assert result["status"] == "fail"
    assert not next(check for check in result["checks"] if check["name"] == "Correct organization")[
        "passed"
    ]
    output = briefing(" ".join(SOURCES[0]["claims"]))
    output.facts.append(Fact(text=SOURCES[2]["claims"][0], source_ids=["aurora_old"]))
    result = grade(TASKS[0], output, SOURCES, "controlled", False, "normal")
    assert result["status"] == "fail"
    assert not next(
        check for check in result["checks"] if check["name"] == "Evidence within reference window"
    )["passed"]


def test_v2_preserves_insufficient_evidence_uncertainty_rule():
    output = AgentOutput(summary="The funding amount cannot be verified.", facts=[])
    assert grade(TASKS[3], output, SOURCES, "controlled", False, "normal")["status"] == "pass"
    output = AgentOutput(
        summary="The funding amount cannot be verified.",
        facts=[{"text": SOURCES[6]["claims"][0], "source_ids": ["quiet_profile"]}],
    )
    assert grade(TASKS[3], output, SOURCES, "controlled", False, "normal")["status"] == "fail"
