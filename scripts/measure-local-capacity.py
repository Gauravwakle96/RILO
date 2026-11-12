"""Repeatable local storage/queue exercise. No model or customer capacity claim."""

import argparse
import asyncio
import json
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rilo.config import Config
from rilo.local_product import dashboard, history
from rilo.schemas import ExperimentCreate
from rilo.storage import Store
from rilo.worker import worker


async def measure(rounds: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="rilo-capacity-") as folder:
        data_dir = Path(folder) / "data"
        data_dir.mkdir()
        store = Store(Config(root=Path(folder), data_dir=data_dir))
        start = time.perf_counter()
        attempts = 0
        for iteration in range(rounds):
            for index in range(10):
                store.create_experiment(
                    ExperimentCreate(
                        name=f"Capacity fixture {iteration}-{index}",
                        agent_ids=["scout", "relay"],
                        task_ids=["company_brief"],
                        scenario_ids=["normal"],
                        repetitions=1,
                    )
                )
            try:
                store.create_experiment(
                    ExperimentCreate(
                        name="Queue overflow",
                        agent_ids=["scout"],
                        task_ids=["company_brief"],
                        scenario_ids=["normal"],
                        repetitions=1,
                    )
                )
                raise AssertionError("Queue limit not enforced")
            except ValueError:
                pass
            for _ in range(10):
                await worker(store, once=True)
            attempts += 20
        elapsed = time.perf_counter() - start

        def read(_):
            tick = time.perf_counter()
            page = history(store, "experiments", page=2, size=5)
            dashboard(store)
            assert page["total"] == rounds * 10
            return (time.perf_counter() - tick) * 1000

        with ThreadPoolExecutor(max_workers=4) as pool:
            latencies = list(pool.map(read, range(100)))
        with store.connection() as connection:
            errors = connection.execute(
                "SELECT count(*) FROM runs WHERE state!='completed'"
            ).fetchone()[0]
        return {
            "method": "temporary-store deterministic fixture exercise; no model inference",
            "rounds": rounds,
            "evaluations": rounds * 10,
            "attempts": attempts,
            "elapsed_seconds": elapsed,
            "noncompleted_runs": errors,
            "reader_threads": 4,
            "history_dashboard_reads": 100,
            "read_latency_ms_median": statistics.median(latencies),
            "read_latency_ms_p95": sorted(latencies)[94],
            "queue_limit": 10,
            "limitations": [
                "Does not measure model throughput, external services, customer first-use success or multi-user hosting.",
                "Measured on this machine under this workload only.",
            ],
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.rounds <= 20:
        parser.error("rounds must be 1–20")
    result = asyncio.run(measure(args.rounds))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
