"""Validated public requests and internal output contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import loopback_url

Short = Annotated[str, Field(min_length=1, max_length=120)]
Identifier = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_\-]+$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Limits(StrictModel):
    max_model_calls: int = Field(default=12, ge=1, le=30)
    max_tool_calls: int = Field(default=6, ge=1, le=20)
    timeout_seconds: int = Field(default=120, ge=5, le=600)


class ExperimentCreate(StrictModel):
    name: Short
    agent_ids: list[Identifier] = Field(min_length=1, max_length=8)
    task_ids: list[Identifier] = Field(min_length=1, max_length=20)
    scenario_ids: list[Literal["normal", "search_timeout", "model_outage", "prompt_injection"]] = (
        Field(min_length=1, max_length=4)
    )
    repetitions: int = Field(default=3, ge=1, le=5)
    engine: Literal["fixture", "bifrost"] = "fixture"
    mode: Literal["controlled", "live"] = "controlled"
    model: str = Field(
        default="ollama/qwen2.5-coder:7b",
        min_length=1,
        max_length=120,
        pattern=r"^[A-Za-z0-9_./:\-]+$",
    )
    limits: Limits = Field(default_factory=Limits)

    @model_validator(mode="after")
    def bounded_matrix(self) -> ExperimentCreate:
        for values in (self.agent_ids, self.task_ids, self.scenario_ids):
            if len(values) != len(set(values)):
                raise ValueError("Selections must not contain duplicate IDs.")
        if (
            len(self.agent_ids) * len(self.task_ids) * len(self.scenario_ids) * self.repetitions
            > 200
        ):
            raise ValueError("An experiment is limited to 200 attempts.")
        if self.mode == "live" and self.engine == "fixture":
            raise ValueError("Live research requires the Bifrost engine.")
        return self


class AgentCreate(StrictModel):
    name: Short
    description: str = Field(default="", max_length=500)
    kind: Literal["http"] = "http"
    endpoint: str = Field(max_length=300)
    version: str = Field(default="1.0.0", min_length=1, max_length=40)

    @field_validator("endpoint")
    @classmethod
    def endpoint_local(cls, value: str) -> str:
        return loopback_url(value)


class TaskCreate(StrictModel):
    title: Short
    description: str = Field(default="", max_length=1000)
    prompt: str = Field(min_length=10, max_length=6000)
    company: str = Field(default="", max_length=120)
    reference_time: datetime
    required_facts: list[str] = Field(min_length=1, max_length=12)
    source_ids: list[Identifier] = Field(min_length=1, max_length=12)

    @field_validator("required_facts")
    @classmethod
    def bounded_facts(cls, values: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > 1000 for item in values):
            raise ValueError("Required facts must be nonempty and at most 1000 characters.")
        return values

    @field_validator("reference_time")
    @classmethod
    def zoned_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Include a timezone in reference_time.")
        return value


class AgentVersionCreate(StrictModel):
    version: str = Field(min_length=1, max_length=40)
    endpoint: str = Field(max_length=300)
    name: Short | None = None
    description: str | None = Field(default=None, max_length=500)

    @field_validator("endpoint")
    @classmethod
    def endpoint_local(cls, value: str) -> str:
        return loopback_url(value)


class SettingsUpdate(StrictModel):
    bifrost_url: str | None = Field(default=None, max_length=300)
    model: str | None = Field(
        default=None, min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_./:\-]+$"
    )

class Fact(StrictModel):
    text: str = Field(min_length=1, max_length=1500)
    source_ids: list[str] = Field(min_length=1, max_length=8)


class AgentOutput(StrictModel):
    summary: str = Field(min_length=1, max_length=6000)
    facts: list[Fact] = Field(max_length=20)


class BaselineCreate(StrictModel):
    experiment_id: Identifier
    name: Short


class ComparisonCreate(StrictModel):
    baseline_id: Identifier
    candidate_id: Identifier
    allow_agent_changes: bool = Field(default=False, strict=True)
