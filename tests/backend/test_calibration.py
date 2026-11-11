import json

from rilo.calibration import CalibrationDataset, score


def test_calibration_preserves_errors_and_reports_per_state_metrics():
    dataset = CalibrationDataset.model_validate(
        {
            "name": "Test",
            "version": "1",
            "items": [
                {"id": "a", "expected": "VERIFIED", "predicted": "VERIFIED", "reviewer": "A", "rationale": "Direct"},
                {"id": "b", "expected": "CONTRADICTED", "predicted": "PARTIALLY VERIFIED", "reviewer": "A", "rationale": "Miss"}
            ]
        }
    )
    result = score(dataset)
    assert result["accuracy"] == 0.5
    assert result["confusion_matrix"]["CONTRADICTED"]["PARTIALLY VERIFIED"] == 1
    assert result["per_state"]["VERIFIED"]["f1"] == 1
    assert "universal" in result["scope"]


def test_published_calibration_fixture_is_valid():
    from pathlib import Path

    value = CalibrationDataset.model_validate_json(
        Path("examples/calibration/repository-claims-v1.json").read_text(encoding="utf-8")
    )
    result = score(value)
    assert result["items"] == 5 and result["accuracy"] == 0.8
    json.dumps(result)
