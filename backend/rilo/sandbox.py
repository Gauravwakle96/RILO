"""Opt-in repository test execution using a constrained preinstalled Docker image."""

from __future__ import annotations

import asyncio
import io
import os
import re
import tarfile
import uuid

PROFILES = {
    "python-unittest": ["python", "-I", "-m", "unittest", "discover", "-v"],
    "node-test": ["node", "--test"],
}


async def run_tests(sources: list[dict], profile: str) -> dict:
    image = os.environ.get("RILO_SANDBOX_IMAGE", "")
    if not re.fullmatch(r"[A-Za-z0-9_./:\-]+@sha256:[a-f0-9]{64}", image):
        return {
            "status": "unavailable",
            "reason": "Set RILO_SANDBOX_IMAGE to a preinstalled image pinned by digest. No dependencies or images are installed automatically.",
            "executed": False,
        }
    command = PROFILES[profile]
    name = "rilo-test-" + uuid.uuid4().hex[:12]

    async def docker(*args, data=None, timeout=15):
        try:
            process = await asyncio.create_subprocess_exec(
                "docker",
                *args,
                stdin=asyncio.subprocess.PIPE if data else asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return 127, b"", b"Docker is not installed."

        async def bounded_read(stream):
            output = bytearray()
            while chunk := await stream.read(65536):
                output.extend(chunk[: max(0, 128000 - len(output))])
            return bytes(output)

        async def exchange():
            if data:
                assert process.stdin is not None
                process.stdin.write(data)
                await process.stdin.drain()
                process.stdin.close()
            stdout, stderr = await asyncio.gather(
                bounded_read(process.stdout), bounded_read(process.stderr)
            )
            await process.wait()
            return process.returncode, stdout, stderr

        try:
            return await asyncio.wait_for(exchange(), timeout=timeout)
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as tar:
        for source in sources:
            from .ingestion import safe_path

            path = safe_path(source["reference"])
            data = source["content"].encode()
            info = tarfile.TarInfo("work/" + path)
            info.size = len(data)
            info.mode = 0o444
            tar.addfile(info, io.BytesIO(data))

    async def execute():
        try:
            code, _, error = await docker(
                "create",
                "--name",
                name,
                "--network=none",
                "--memory=512m",
                "--memory-swap=512m",
                "--cpus=1",
                "--pids-limit=64",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--user=65534:65534",
                "--workdir=/work",
                "--tmpfs=/work:rw,noexec,nosuid,size=32m,uid=65534,gid=65534,mode=0700",
                "--tmpfs=/tmp:rw,noexec,nosuid,size=64m",
                "--log-driver=local",
                "--log-opt=max-size=1m",
                "--log-opt=max-file=1",
                "--log-opt=compress=false",
                "--pull=never",
                "--entrypoint=/bin/sleep",
                image,
                "90",
            )
            if code:
                return {
                    "status": "unavailable",
                    "executed": False,
                    "reason": error.decode(errors="replace"),
                }
            code, _, error = await docker("start", name)
            if code:
                return {
                    "status": "unavailable",
                    "executed": False,
                    "reason": "Isolated container could not start: "
                    + error.decode(errors="replace"),
                }
            code, _, error = await docker(
                "exec",
                "-i",
                name,
                "tar",
                "--no-same-owner",
                "-xf",
                "-",
                "-C",
                "/work",
                "--strip-components=1",
                data=archive.getvalue(),
            )
            if code:
                return {
                    "status": "failed",
                    "executed": False,
                    "reason": "Could not copy captured sources into the isolated container.",
                }
            code, out, error = await docker("exec", name, *command, timeout=60)
            exit_code = code
            return {
                "status": "passed" if exit_code == 0 else "failed",
                "executed": True,
                "exit_code": exit_code,
                "stdout": out.decode(errors="replace"),
                "stderr": error.decode(errors="replace"),
                "command": command,
                "image": image,
                "network": "none",
                "timeout_seconds": 60,
                "scope": "Captured source subset only; no dependency installation",
            }
        except TimeoutError:
            return {
                "status": "timed_out",
                "executed": True,
                "reason": "Isolated test exceeded its time limit.",
            }

    result: dict = {}
    try:
        result.update(await execute())
    finally:
        try:
            code, _, error = await docker("rm", "--force", name)
            result["cleanup"] = {
                "status": "completed" if code == 0 else "failed",
                "container": name,
                "reason": error.decode(errors="replace") if code else None,
            }
        except (TimeoutError, OSError) as exc:
            result["cleanup"] = {
                "status": "failed",
                "container": name,
                "reason": type(exc).__name__,
            }
        if result["cleanup"]["status"] == "failed":
            import logging

            logging.getLogger(__name__).warning(
                "Sandbox cleanup failed for %s: %s", name, result["cleanup"]["reason"]
            )
    return result
