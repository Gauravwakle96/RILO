"""The documented local launcher starts and stops its owned service process tree."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


def test_local_serve_custom_port_and_shutdown(tmp_path: Path):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    log_path = tmp_path / "services.log"
    environment = {**os.environ, "RILO_DATA_DIR": str(tmp_path / "workspace")}
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "rilo.cli",
                "--data-dir",
                str(tmp_path / "workspace"),
                "serve",
                "--port",
                str(port),
            ],
            stdout=log,
            stderr=log,
            env=environment,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
        try:
            deadline = time.monotonic() + 12
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=0.5
            ) as client:
                while True:
                    try:
                        healthy = client.get("/health").status_code == 200
                    except httpx.HTTPError:
                        healthy = False
                    if healthy:
                        break
                    assert process.poll() is None, log_path.read_text()
                    assert time.monotonic() < deadline, log_path.read_text()
                    time.sleep(0.15)
                response = client.get(
                    "/api/v1/session", headers={"Origin": f"http://127.0.0.1:{port}"}
                )
                assert response.status_code == 200
                assert "httponly" in response.headers["set-cookie"].lower()
            process.send_signal(
                signal.CTRL_BREAK_EVENT if sys.platform == "win32" else signal.SIGINT
            )
            assert process.wait(timeout=12) == 0, log_path.read_text()
            with socket.socket() as probe:
                probe.settimeout(0.5)
                assert probe.connect_ex(("127.0.0.1", port)) != 0
        finally:
            if process.poll() is None:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                else:
                    process.terminate()
                process.wait(timeout=12)
