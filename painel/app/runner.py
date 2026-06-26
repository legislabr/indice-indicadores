import asyncio
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR, SCRIPT_PATH, LEGISLATURA_DEFAULT

DATA = Path(DATA_DIR)
RUNNING: subprocess.Popen | None = None
LOG_PATH: Path | None = None
EXIT_CODE: int | None = None
STARTED_AT: str | None = None
FINISHED_AT: str | None = None
LAST_ARGS: dict | None = None
_guard = asyncio.Lock()


def _logs_dir() -> Path:
    d = DATA / "logs"
    d.makedirs(parents=True, exist_ok=True)
    return d


def is_running() -> bool:
    return RUNNING is not None and RUNNING.poll() is None


def _tail(path: Path, n: int = 200) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        return "".join(lines[-n:])
    except OSError:
        return ""


def status() -> dict:
    return {
        "running": is_running(),
        "exit_code": EXIT_CODE,
        "started_at": STARTED_AT,
        "finished_at": FINISHED_AT,
        "args": LAST_ARGS,
        "log_path": str(LOG_PATH) if LOG_PATH else None,
        "log_tail": _tail(LOG_PATH) if LOG_PATH else "",
    }


async def start_run(ano_final: int, mes: str = "", legislatura: int = LEGISLATURA_DEFAULT) -> dict:
    global RUNNING, LOG_PATH, EXIT_CODE, STARTED_AT, FINISHED_AT, LAST_ARGS

    async with _guard:
        if is_running():
            raise RuntimeError("Já existe uma extração em execução.")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = _logs_dir() / f"run_{ts}.log"

        cmd = [
            sys.executable,
            SCRIPT_PATH,
            "--ano-final", str(ano_final),
            "--ano-ini-legis", "2023",
            "--legislatura-atual", str(legislatura),
        ]
        if mes:
            cmd += ["--mes", str(mes).zfill(2)]

        log_fp = open(log_path, "ab", buffering=0)
        log_fp.write(f"$ {' '.join(cmd)}\n\n".encode())

        proc = subprocess.Popen(
            cmd,
            cwd=str(DATA),
            stdout=log_fp,
            stderr=subprocess.STDOUT,
        )

        RUNNING = proc
        LOG_PATH = log_path
        EXIT_CODE = None
        STARTED_AT = datetime.now().isoformat(timespec="seconds")
        FINISHED_AT = None
        LAST_ARGS = {"ano_final": ano_final, "mes": mes or None, "legislatura": legislatura}

        asyncio.create_task(_waiter(proc))

    return status()


async def _waiter(proc: subprocess.Popen) -> None:
    global EXIT_CODE, FINISHED_AT
    code = await asyncio.to_thread(proc.wait)
    EXIT_CODE = code
    FINISHED_AT = datetime.now().isoformat(timespec="seconds")
