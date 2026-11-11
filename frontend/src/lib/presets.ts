import type { Catalog, ExperimentPreset } from "../types";

export function recoveryPreset(catalog: Catalog): ExperimentPreset {
  return {
    name: "Search recovery · first experiment",
    agent_ids: catalog.agents
      .filter((agent) => ["scout", "relay"].includes(agent.id))
      .map((agent) => agent.id),
    task_ids: catalog.tasks.some((task) => task.id === "entity_match")
      ? ["entity_match"]
      : catalog.tasks.slice(0, 1).map((task) => task.id),
    scenario_ids: ["normal", "search_timeout"],
    engine: "fixture",
    mode: "controlled",
    repetitions: 3,
  };
}
