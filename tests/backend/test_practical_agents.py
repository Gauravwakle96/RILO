"""Practical profiles use the existing pinned, independent evidence workflow."""

import copy
import json

import pytest
from rilo.catalog import AGENTS
from rilo.engine import RunContext
from rilo.schemas import ExperimentCreate
from rilo.snapshots import Snapshots
from rilo.storage import Store
from rilo.task_checks import TaskCheck, validate_checks
from rilo.worker import worker
from rilo.workspace_contracts import ConversationCreate, TurnCreate
from rilo.workspace_engine import generation_messages
from rilo.workspace_store import WorkspaceStore, profiles

PRACTICAL = [a for a in AGENTS if a["config"].get("catalog_group") == "practical"]


def test_catalog_has_four_distinct_useful_roles_and_valid_examples(store):
    practical = [p for p in profiles(store) if p["catalog_group"] == "practical"]
    assert {p["role"] for p in practical} == {"support", "documents", "coding", "research"}
    assert len(practical) == 4
    for profile in practical:
        assert profile["example"]["category"] in profile["supported_tasks"]
        checks = [TaskCheck.model_validate(check) for check in profile["example"]["checks"]]
        validate_checks(checks)
        assert len(checks) >= 2
        assert profile["limitations"]
        assert profile["version"] in {v["version"] for v in store.agent_versions(profile["id"])}


def test_existing_profiles_upgrade_without_changing_saved_versions_or_user_config(config):
    store = Store(config)
    old = copy.deepcopy(next(a for a in PRACTICAL if a["id"] == "repo_analyst"))
    old.update(name="Repo Analyst", version="2.0.0")
    old["config"] = {"workspace_categories": ["repository"], "retries": 1, "model": "ollama/custom"}
    with store.transaction() as connection:
        connection.execute(
            "UPDATE catalog SET data=? WHERE kind='agent' AND id=?", (json.dumps(old), old["id"])
        )
        connection.execute("DELETE FROM agent_versions WHERE agent_id=?", (old["id"],))
    restarted = Store(config)
    current = restarted.item("agent", old["id"])
    assert current["name"] == "Coding Assistant" and current["version"] == "2.1.1"
    assert current["config"]["model"] == "ollama/custom"
    versions = {v["version"]: v for v in restarted.agent_versions(old["id"])}
    assert versions["2.0.0"]["name"] == "Repo Analyst"
    assert "profile_instructions" not in versions["2.0.0"]["config"]
    assert versions["2.1.1"]["config"]["profile_instructions"]
    assert len(Store(config).agent_versions(old["id"])) == 2


def test_support_upgrade_preserves_custom_model_and_prior_failed_prompt(config):
    store = Store(config)
    old = copy.deepcopy(store.item("agent", "customer_support"))
    old["version"] = "1.0.0"
    old["config"].update(
        model="ollama/custom",
        profile_instructions="Earlier instructions",
        example={"task": "Earlier task"},
    )
    with store.transaction() as connection:
        connection.execute(
            "UPDATE catalog SET data=? WHERE kind='agent' AND id=?", (json.dumps(old), old["id"])
        )
        connection.execute("DELETE FROM agent_versions WHERE agent_id=?", (old["id"],))
    restarted = Store(config)
    revised = restarted.item("agent", old["id"])
    assert revised["version"] == "1.0.1"
    assert revised["config"]["model"] == "ollama/custom"
    assert "review is needed" in revised["config"]["profile_instructions"]
    assert revised["config"]["example"]["task"] != "Earlier task"
    versions = {v["version"]: v for v in restarted.agent_versions(old["id"])}
    assert versions["1.0.0"]["config"]["profile_instructions"] == "Earlier instructions"


@pytest.mark.parametrize("profile", PRACTICAL, ids=lambda a: a["id"])
async def test_each_practical_profile_executes_paired_with_shared_sources_and_private_history(
    store, monkeypatch, profile
):
    seen = []

    async def completion(self, messages, **kwargs):
        seen.append((self.run["agent_id"], self.spec.model, messages))
        source = self.evidence[0]
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": self.run["agent_id"] + " private answer",
                                "findings": [
                                    {
                                        "title": "Captured observation",
                                        "claim": source["content"],
                                        "citations": [
                                            {"source_id": source["id"], "quote": source["content"]}
                                        ],
                                    }
                                ],
                            }
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(RunContext, "completion", completion)
    category = profile["config"]["example"]["category"]
    source_type = "repository" if category == "repository" else "text"
    snapshot = Snapshots(store).create(
        category,
        [
            {
                "type": source_type,
                "reference": "policy.txt",
                "content": "Policy records are retained for 30 days.",
            }
        ],
    )
    workspace = WorkspaceStore(store)
    conversation = workspace.create(
        ConversationCreate(
            title=profile["name"],
            category=category,
            slots=[
                {"agent_id": profile["id"], "model": "ollama/first", "instructions": "Be concise."},
                {
                    "agent_id": profile["id"],
                    "model": "ollama/second",
                    "instructions": "Explain conditions.",
                },
            ],
        )
    )
    first = workspace.turn(
        conversation["id"],
        TurnCreate(
            message="Answer using the policy.",
            snapshot_id=snapshot["id"],
            checks=[
                {"id": "references", "name": "Reference validity", "type": "citations-valid"},
            ],
        ),
    )
    await worker(store, once=True)
    saved = workspace.get(conversation["id"])["turns"][0]
    assert all(r["outcome"] == "completed" for r in saved["runs"])
    assert all(r["assessment"]["task_checks"]["status"] == "pass" for r in saved["runs"])
    assert seen[0][2][-1] == seen[1][2][-1]
    assert {model for _, model, _ in seen} == {"ollama/first", "ollama/second"}
    assert all(
        profile["config"]["profile_instructions"] in messages[0]["content"]
        for _, _, messages in seen
    )
    workspace.turn(conversation["id"], TurnCreate(message="Recall your response."))
    await worker(store, once=True)
    for agent_id, _, messages in seen[2:]:
        sibling = "slot_b" if agent_id == "slot_a" else "slot_a"
        assert agent_id + " private answer" in str(messages)
        assert sibling + " private answer" not in str(messages)
    assert store.experiment(first["id"])["manifest"]["snapshot"]["id"] == snapshot["id"]


def test_support_policy_is_pinned_and_legacy_profiles_keep_prior_prompt(store):
    support = store.item("agent", "customer_support")
    prompt = generation_messages(
        {
            "workspace": {
                "histories": {},
                "prompt": "Refund request",
                "category": "chat",
                "search_provider": "off",
            },
            "sources": [],
            "selection": {},
        },
        support,
    )[0]["content"]
    assert "NEEDS HUMAN SUPPORT" in prompt and "Do not invent exceptions" in prompt
    assert "open tickets" in prompt and "supplied support policies" in prompt
    legacy = copy.deepcopy(store.item("agent", "repo_analyst"))
    legacy["config"] = {"workspace_categories": ["repository"]}
    prompt = generation_messages(
        {
            "workspace": {
                "histories": {},
                "prompt": "Explain code",
                "category": "repository",
                "search_provider": "off",
            },
            "sources": [],
            "selection": {},
        },
        legacy,
    )[0]["content"]
    assert "Static evidence is not proof of exploitability" in prompt


def test_practical_profiles_reject_incompatible_workspace_and_legacy_benchmark(store):
    with pytest.raises(ValueError, match="does not support"):
        WorkspaceStore(store).create(
            ConversationCreate(
                title="Wrong role",
                category="repository",
                slots=[{"agent_id": "customer_support"}, {"agent_id": "relay"}],
            )
        )
    with pytest.raises(ValueError, match="Task-specific"):
        store.create_experiment(
            ExperimentCreate(
                name="Wrong engine",
                agent_ids=["customer_support"],
                task_ids=["company_brief"],
                scenario_ids=["normal"],
            )
        )


async def test_invalid_quotes_trigger_bounded_deterministic_recovery(store, monkeypatch):
    calls = {}

    async def completion(self, messages, **kwargs):
        count = calls.get(self.run["agent_id"], 0) + 1
        calls[self.run["agent_id"]] = count
        source = self.evidence[0]
        quote = "invented source quotation" if count == 1 else source["content"]
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "Observed policy",
                                "findings": [
                                    {
                                        "title": "Policy",
                                        "claim": "Policy",
                                        "citations": [{"source_id": source["id"], "quote": quote}],
                                    }
                                ],
                            }
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(RunContext, "completion", completion)
    workspace = WorkspaceStore(store)
    conv = workspace.create(
        ConversationCreate(
            title="Citation repair", slots=[{"agent_id": "document_analyst"}, {"agent_id": "scout"}]
        )
    )
    exp = workspace.turn(
        conv["id"],
        TurnCreate(
            message="Quote the policy.", inputs={"text": "Audit records are retained for 30 days."}
        ),
    )
    await worker(store, once=True)
    runs = workspace.get(conv["id"])["turns"][0]["runs"]
    assert calls == {"slot_a": 2, "slot_b": 1}
    repaired = next(r for r in runs if r["agent_id"] == "slot_a")
    baseline = next(r for r in runs if r["agent_id"] == "slot_b")
    assert repaired["assessment"]["metrics"]["citation_validity"] == 1
    assert baseline["assessment"]["metrics"]["citation_validity"] == 0
    warning = next(e for e in repaired["events"] if e["type"] == "citation_warning")
    assert (
        warning["data"]["output"]["findings"][0]["citations"][0]["quote"]
        == "invented source quotation"
    )
    assert store.experiment(exp["id"])["state"] == "completed"
