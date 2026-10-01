"""Writes to the kanban board go through Hermes' public CLI, never into kanban.db."""
from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def hermes_bin(home: Path) -> str:
    env = os.environ.get("HERMES_BIN")
    if env and Path(env).exists():
        return env
    return str(home / "hermes-agent" / ".hermes" / "bin" / "hermes.exe")


async def run(home: Path, *args: str, timeout: float = 60) -> str:
    env = os.environ | {"HERMES_HOME": str(home), "PYTHONIOENCODING": "utf-8"}
    proc = await asyncio.create_subprocess_exec(
        hermes_bin(home), *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        env=env, creationflags=NO_WINDOW)
    out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    text = out.decode("utf-8", errors="replace")
    if proc.returncode:
        raise RuntimeError(f"hermes {' '.join(args[:2])} failed ({proc.returncode}): {text[-400:]}")
    return text


async def comment(home: Path, task_id: str, body: str, author: str = "you (sage-os)") -> str:
    return await run(home, "kanban", "comment", task_id, body, "--author", author)


async def unblock(home: Path, task_id: str) -> str:
    return await run(home, "kanban", "unblock", task_id)
