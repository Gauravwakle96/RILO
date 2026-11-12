"""Typed contracts shared by task workspaces; no provider-specific execution state."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .schemas import AgentOutput, Fact, Identifier, Limits, StrictModel
from .task_checks import TaskCheck, validate_checks

Category = Literal["chat", "repository", "documents", "website", "search"]


class TaskInput(StrictModel):
    url: str | None = Field(default=None, max_length=2000)
    upload_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    text: str = Field(default="", max_length=20000)
    max_pages: int = Field(default=3, ge=1, le=10)
    max_depth: int = Field(default=1, ge=0, le=2)
    run_tests: bool = False
    dependency_advisories: bool = False
    test_profile: Literal["python-unittest", "node-test"] = "python-unittest"
    repository_ref: str | None = Field(default=None, min_length=1, max_length=200)
    source_references: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def valid_references(self):
        if any(not value or len(value) > 2000 for value in self.source_references) or len(
            set(self.source_references)
        ) != len(self.source_references):
            raise ValueError(
                "Source references must be unique, nonempty captured references up to 2000 characters."
            )
        return self


class AgentSlot(StrictModel):
    agent_id: Identifier
    version: str | None = Field(default=None, max_length=40)
    model: str | None = Field(
        default=None, min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_./:\-]+$"
    )
    instructions: str = Field(default="", max_length=1200)
    temperature: float = Field(default=0, ge=0, le=2)
    max_retries: int | None = Field(default=None, ge=0, le=1)


class ConversationCreate(StrictModel):
    title: str = Field(min_length=1, max_length=120)
    category: Category = "chat"
    agent_ids: list[Identifier] = Field(
        default_factory=lambda: ["scout", "relay"], min_length=2, max_length=2
    )
    model: str = Field(
        default="ollama/qwen2.5-coder:7b",
        min_length=1,
        max_length=120,
        pattern=r"^[A-Za-z0-9_./:\-]+$",
    )
    search_provider: Literal["off", "tavily"] = "off"
    slots: list[AgentSlot] | None = Field(default=None, min_length=2, max_length=2)
    semantic_review: bool = False
    limits: Limits = Field(
        default_factory=lambda: Limits(max_model_calls=2, max_tool_calls=2, timeout_seconds=180)
    )

    @model_validator(mode="after")
    def distinct_agents(self):
        if not self.slots and self.agent_ids[0] == self.agent_ids[1]:
            raise ValueError("Choose two independent agent profiles.")
        return self


class TurnCreate(StrictModel):
    message: str = Field(min_length=1, max_length=6000)
    inputs: TaskInput = Field(default_factory=TaskInput)
    snapshot_id: Identifier | None = None
    checks: list[TaskCheck] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def unique_checks(self):
        validate_checks(self.checks)
        return self


class CandidateCreate(StrictModel):
    slots: list[AgentSlot] | None = Field(default=None, min_length=2, max_length=2)


class RecordAction(StrictModel):
    action: Literal["archive", "restore", "delete"]
    confirmation: str = Field(default="", max_length=120)


class HumanReview(StrictModel):
    finding_id: Identifier
    state: Literal[
        "VERIFIED", "PARTIALLY VERIFIED", "UNSUPPORTED", "CONTRADICTED", "NEEDS MANUAL REVIEW"
    ]
    rationale: str = Field(min_length=1, max_length=2000)


class Citation(StrictModel):
    source_id: Identifier
    quote: str = Field(min_length=1, max_length=1500)
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    page: int | None = Field(default=None, ge=1)


class Finding(StrictModel):
    title: str = Field(min_length=1, max_length=180)
    claim: str = Field(min_length=1, max_length=2000)
    severity: Literal["info", "low", "medium", "high", "critical"] = "info"
    explanation: str = Field(default="", max_length=2500)
    citations: list[Citation] = Field(default_factory=list, max_length=8)


class WorkspaceOutput(AgentOutput):
    facts: list[Fact] = Field(default_factory=list, max_length=20)
    findings: list[Finding] = Field(default_factory=list, max_length=20)


class WorkspaceTask(StrictModel):
    category: Category
    prompt: str = Field(min_length=1, max_length=6000)
    inputs: TaskInput = Field(default_factory=TaskInput)
    snapshot_id: Identifier | None = None
    conversation_id: Identifier
    turn_id: Identifier
    search_provider: Literal["off", "tavily"] = "off"
    histories: dict[str, list[dict[str, str]]] = Field(default_factory=dict)
