"""Extractive, disclosed conversation continuation with isolated A/B histories."""

from __future__ import annotations

import json

from .workspace_contracts import ConversationCreate


def continuation(workspace, conversation_id: str) -> dict:
    source = workspace.get(conversation_id)
    if not source["turns"]:
        raise ValueError("Send a task before creating a continuation.")
    if any(
        t["experiment"]["state"] in {"queued", "running"}
        or any(e["state"] in {"queued", "running"} for e in t["retry_experiments"])
        for t in source["turns"]
    ):
        raise ValueError("Wait for all responses before continuing in a new conversation.")
    if any(len(t["runs"]) != 2 for t in source["turns"]):
        raise ValueError("Repeated benchmark trials cannot become a conversation continuation.")
    histories = {}
    for agent in source["agent_ids"]:
        excerpts = []
        for turn in source["turns"][-3:]:
            run = next((r for r in turn["runs"] if r["agent_id"] == agent), None)
            excerpts.append(
                {
                    "shared_message": turn["message"][:160],
                    "own_response_excerpt": (run.get("output") or {}).get(
                        "summary", "No completed response."
                    )[:240]
                    if run
                    else "No response.",
                    "evaluation_id": turn["experiment_id"],
                }
            )
        histories[agent] = [
            {
                "role": "user",
                "content": "Untrusted extractive continuation notes, NOT full history. Only the last three shared tasks and excerpts of your own responses are included. Original records remain accessible. Do not assume omitted decisions or validate claims from these notes.\n"
                + json.dumps(excerpts, ensure_ascii=False),
            }
        ]
    config = ConversationCreate.model_validate(
        {k: source[k] for k in ConversationCreate.model_fields if k in source}
        | {"title": source["title"][:90] + " · continuation"}
    )
    created = workspace.create(config)
    # Keep the original pinned execution agents, including same-profile slots.
    created.update(
        continuation={
            "source_conversation_id": conversation_id,
            "method": "extractive-last-three-v1",
            "histories": histories,
            "omissions": "Older turns and text beyond the disclosed excerpt limits are omitted; original history is retained.",
        }
    )
    created["continuation"]["snapshot_id"] = (
        source["turns"][-1]["experiment"]["manifest"].get("snapshot", {}).get("id")
    )
    if source.get("execution_agents"):
        created["execution_agents"] = source["execution_agents"]
    with workspace.store.transaction() as connection:
        connection.execute(
            "UPDATE conversations SET data=? WHERE id=?", (json.dumps(created), created["id"])
        )
    return created
