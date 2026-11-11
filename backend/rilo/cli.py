"""Command-line interface for local Rilo experiments and regression checks."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import __version__
from .client import RiloClient, RiloError, pretty


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="rilo", description="Test and compare your AI agents locally."
    )
    result.add_argument("--url", default="http://127.0.0.1:8018", help="Local Rilo API URL")
    result.add_argument("--data-dir", default=os.environ.get("RILO_DATA_DIR", ".rilo"))
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("version", help="Show the installed version")
    serve = commands.add_parser("serve", help="Run API, built dashboard, and separate worker")
    serve.add_argument("--port", type=int, default=8018)
    serve.add_argument(
        "--no-worker", action="store_true", help="Run only API; start worker separately"
    )
    commands.add_parser("doctor", help="Check real integration status and configuration")
    commands.add_parser("agents", help="List registered agents")
    commands.add_parser("tasks", help="List task definitions")
    commands.add_parser("experiments", help="List persisted experiments")
    run = commands.add_parser("run", help="Queue an experiment from a JSON specification")
    run.add_argument("spec", type=Path)
    run.add_argument("--wait", action="store_true")
    run.add_argument("--timeout", type=float, default=900)
    run.add_argument("--idempotency-key")
    demo = commands.add_parser("demo", help="Execute a labeled deterministic demonstration")
    demo.add_argument(
        "--full", action="store_true", help="Five tasks, three trials, four conditions"
    )
    demo.add_argument("--wait", action="store_true")
    demo.add_argument("--name", default="Recovery demonstration")
    show = commands.add_parser("show", help="Inspect a persisted experiment")
    show.add_argument("id")
    cancel = commands.add_parser("cancel", help="Request experiment cancellation")
    cancel.add_argument("id")
    report = commands.add_parser("report", help="Download an evidence report")
    report.add_argument("id")
    report.add_argument("--output", required=True, type=Path)
    report.add_argument("--format", choices=("json", "csv"), default="json")
    baseline = commands.add_parser("baseline", help="Save an experiment as a baseline")
    baseline.add_argument("id")
    baseline.add_argument("--name", required=True)
    compare = commands.add_parser("compare", help="Compare candidate and baseline experiments")
    compare.add_argument("--baseline", required=True)
    compare.add_argument("--candidate", required=True)
    compare.add_argument(
        "--allow-agent-changes",
        action="store_true",
        help="Declare agent code/configuration changes as the candidate variable",
    )
    compare.add_argument(
        "--require-pass", action="store_true", help="Exit 1 on fail, 2 on inconclusive"
    )
    return result


def serve(args: argparse.Namespace) -> int:
    if not 1024 <= args.port <= 65535:
        raise RiloError("Use a port between 1024 and 65535.")
    environment = os.environ.copy()
    environment["RILO_DATA_DIR"] = str(Path(args.data_dir).resolve())
    environment["RILO_PORT"] = str(args.port)
    process_args: list[list[str]] = [
        [
            sys.executable,
            "-m",
            "uvicorn",
            "rilo.api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
        ]
    ]
    if not args.no_worker:
        process_args.append([sys.executable, "-m", "rilo.worker"])
    children: list[subprocess.Popen[Any]] = []
    interrupted = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal interrupted
        interrupted = True

    previous = signal.signal(signal.SIGINT, stop)
    previous_break = signal.signal(signal.SIGBREAK, stop) if sys.platform == "win32" else None
    previous_term = signal.signal(signal.SIGTERM, stop) if sys.platform != "win32" else None
    try:
        for command in process_args:
            children.append(subprocess.Popen(command, env=environment))
        print(f"Rilo: http://127.0.0.1:{args.port}", flush=True)
        print("The API and worker retain experiments in the local data folder.", flush=True)
        while not interrupted:
            for child in children:
                code = child.poll()
                if code is not None:
                    print(f"A Rilo service stopped (exit {code}).", file=sys.stderr)
                    return code or 1
            time.sleep(0.25)
        return 0
    finally:
        signal.signal(signal.SIGINT, previous)
        if previous_break is not None:
            signal.signal(signal.SIGBREAK, previous_break)
        if previous_term is not None:
            signal.signal(signal.SIGTERM, previous_term)
        for child in children:
            if child.poll() is None:
                if sys.platform == "win32":
                    # Windows venv launchers have a real interpreter child. Ending
                    # only the launcher leaves the worker and API running.
                    subprocess.run(
                        ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                else:
                    child.terminate()
        for child in children:
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "version":
            print(f"Rilo {__version__}")
            return 0
        if args.command == "serve":
            return serve(args)
        with RiloClient(args.url, args.data_dir) as client:
            if args.command == "doctor":
                print(pretty(client.request("GET", "settings")))
            elif args.command == "agents":
                print(pretty(client.agents()))
            elif args.command == "tasks":
                print(pretty(client.tasks()))
            elif args.command == "experiments":
                print(pretty(client.experiments()))
            elif args.command == "run":
                spec = json.loads(args.spec.read_text(encoding="utf-8"))
                if not isinstance(spec, dict):
                    raise RiloError("An experiment specification must be a JSON object.")
                result = client.run(spec, idempotency_key=args.idempotency_key)
                if args.wait:
                    result = client.wait(result["id"], timeout=args.timeout)
                print(pretty(result))
            elif args.command == "demo":
                tasks = [item["id"] for item in client.tasks()]
                spec = {
                    "name": args.name,
                    "agent_ids": ["scout", "relay"],
                    "task_ids": tasks[:5] if args.full else tasks[:1],
                    "scenario_ids": [
                        "normal",
                        "search_timeout",
                        "model_outage",
                        "prompt_injection",
                    ],
                    "repetitions": 3 if args.full else 1,
                    "engine": "fixture",
                    "mode": "controlled",
                }
                result = client.run(spec)
                if args.wait:
                    result = client.wait(result["id"])
                print(pretty(result))
            elif args.command == "show":
                print(pretty(client.experiment(args.id)))
            elif args.command == "cancel":
                print(pretty(client.cancel(args.id)))
            elif args.command == "report":
                client.export(args.id, args.output, format=args.format)
                print(f"Saved report: {args.output}")
            elif args.command == "baseline":
                print(pretty(client.baseline(args.id, args.name)))
            elif args.command == "compare":
                result = client.compare(
                    args.baseline, args.candidate, allow_agent_changes=args.allow_agent_changes
                )
                print(pretty(result))
                if args.require_pass:
                    return {"pass": 0, "fail": 1, "inconclusive": 2}.get(
                        result.get("gate", {}).get("status"), 2
                    )
        return 0
    except (RiloError, OSError, ValueError) as exc:
        print(f"Rilo: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
