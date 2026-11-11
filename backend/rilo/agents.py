"""Two independent research workflows and a bounded local HTTP adapter."""

from __future__ import annotations

import asyncio
from typing import TypedDict

import httpx
from langgraph.graph import END, START, StateGraph

from .engine import InjectedFault, InvalidOutput, RunContext, bounded_json, filter_evidence
from .schemas import AgentOutput


async def scout(context: RunContext) -> AgentOutput:
    context.event("step", "Scout: search once", {"framework": "Plain Python"})
    evidence = await context.search(context.task["company"] + " recent updates")
    context.event("step", "Scout: synthesize once", {"recovery_attempts": 0})
    return await context.synthesize(evidence, robust=False)


class RelayState(TypedDict):
    evidence: list[dict]
    output: dict


async def relay(context: RunContext) -> AgentOutput:
    async def research(state: RelayState) -> dict:
        evidence: list[dict] = []
        queries = [context.task["company"] + " recent updates"]
        if context.task.get("rubric") == "multi":
            queries = [
                context.task["company"] + " product launch",
                context.task["company"] + " partnership leadership",
            ]
        for query in queries:
            for attempt in range(3):
                try:
                    values = await context.search(query)
                    evidence.extend(
                        item
                        for item in values
                        if item["id"] not in {source["id"] for source in evidence}
                    )
                    break
                except InjectedFault:
                    if attempt == 2:
                        raise
                    context.event(
                        "recovery",
                        "Relay: retry eligible search",
                        {"attempt": attempt + 1, "bounded_retries": 2},
                    )
                    await asyncio.sleep(0.04)
        context.event(
            "step",
            "Relay: filter evidence by entity and date",
            {"framework": "LangGraph", "before": len(evidence)},
        )
        selected = filter_evidence(context.task, evidence)
        context.event(
            "evidence_filter",
            "Applicable evidence selected",
            {
                "before": len(evidence),
                "after": len(selected),
                "source_ids": [item["id"] for item in selected],
            },
        )
        return {"evidence": selected}

    async def synthesis(state: RelayState) -> dict:
        for attempt in range(3):
            try:
                output = await context.synthesize(state["evidence"], robust=True)
                return {"output": output.model_dump()}
            except (InjectedFault, InvalidOutput):
                if attempt == 2:
                    raise
                context.event(
                    "recovery",
                    "Relay: retry synthesis",
                    {"attempt": attempt + 1, "bounded_retries": 2},
                )
                await asyncio.sleep(0.04)
        raise RuntimeError("Unreachable retry state")

    graph = StateGraph(RelayState)
    graph.add_node("research", research)
    graph.add_node("synthesis", synthesis)
    graph.add_edge(START, "research")
    graph.add_edge("research", "synthesis")
    graph.add_edge("synthesis", END)
    context.event("step", "Relay: enter LangGraph workflow", {"nodes": ["research", "synthesis"]})
    result = await graph.compile().ainvoke({"evidence": [], "output": {}})
    return AgentOutput.model_validate(result["output"])


async def http_agent(context: RunContext, agent: dict) -> AgentOutput:
    """Final-output adapter; missing tracing/fault capabilities remain explicit."""
    context.check()
    context.event(
        "adapter_request",
        "Invoke local HTTP agent",
        {"endpoint": agent["config"]["endpoint"], "observation_coverage": "final_output_only"},
    )
    async with httpx.AsyncClient(
        timeout=context.spec.limits.timeout_seconds, trust_env=False, follow_redirects=False
    ) as client:
        response = await bounded_json(
            client,
            "POST",
            agent["config"]["endpoint"],
            json={
                "run_id": context.run["id"],
                "task": {key: context.task[key] for key in ("prompt", "company", "reference_time")},
                "evidence": [
                    {key: item.get(key) for key in ("id", "title", "content", "published_at")}
                    for item in context.sources
                    if item["id"] in context.task["source_ids"]
                ],
                "limits": context.spec.limits.model_dump(),
            },
        )
    context.check()
    return AgentOutput.model_validate(response.get("output", response))
