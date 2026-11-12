"""Declarative task checks; this is deliberately not arbitrary Promptfoo configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .schemas import Identifier, StrictModel


class TaskCheck(StrictModel):
    id: Identifier
    name: str = Field(min_length=1, max_length=120)
    type: Literal[
        "equals",
        "contains",
        "icontains",
        "not-contains",
        "not-icontains",
        "is-json",
        "json-field-equals",
        "max-length",
        "citations-valid",
        "has-findings",
    ]
    value: str | None = Field(default=None, max_length=2000)
    target: Literal["summary", "response"] = "summary"

    @model_validator(mode="after")
    def literal_value(self):
        if self.type in {"is-json", "citations-valid", "has-findings"}:
            if self.value is not None:
                raise ValueError("JSON checks do not accept a schema or value.")
        elif not self.value or not self.value.strip():
            raise ValueError("Text checks require a nonempty expected value.")
        if self.type == "max-length" and (
            not self.value or not self.value.isdigit() or not 1 <= int(self.value) <= 100000
        ):
            raise ValueError("Maximum length must be a positive integer up to 100000.")
        if self.type == "json-field-equals":
            import json

            try:
                rule = json.loads(self.value or "")
                if (
                    not isinstance(rule, dict)
                    or set(rule) != {"path", "value"}
                    or not isinstance(rule["path"], str)
                    or not rule["path"]
                    or len(rule["path"]) > 150
                ):
                    raise ValueError
            except (ValueError, TypeError):
                raise ValueError('Use JSON {"path":"field.name","value":"expected"}.') from None
        if self.value and self.value.strip().lower().startswith(("file://", "package:")):
            raise ValueError("Checks accept literal text only, not file or package references.")
        return self


def validate_checks(checks: list[TaskCheck]) -> list[TaskCheck]:
    if len({check.id for check in checks}) != len(checks):
        raise ValueError("Each success check needs a unique ID.")
    return checks
