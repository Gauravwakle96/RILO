"""Run a real persisted fixture demonstration through the local Python SDK.

This exercises the product without model or research API charges. It is not a
live AI benchmark. Start Rilo before running: uv run python examples/compare.py.
"""

from rilo.client import RiloClient


def main() -> None:
    with RiloClient() as client:
        task_id = client.tasks()[0]["id"]
        experiment = client.run(
            {
                "name": "SDK recovery comparison",
                "agent_ids": ["scout", "relay"],
                "task_ids": [task_id],
                "scenario_ids": ["normal", "search_timeout", "prompt_injection"],
                "repetitions": 3,
                "engine": "fixture",
                "mode": "controlled",
            }
        )
        result = client.wait(experiment["id"])
        print(f"{result['name']}: {result['state']}")
        print(f"Accounted attempts: {result['progress']}")
        for metric in result["agent_metrics"]:
            print(f"{metric['agent_name']}: {metric['passed']}/{metric['total']} passed")


if __name__ == "__main__":
    main()
