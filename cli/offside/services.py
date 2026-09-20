"""Start and stop the local Offside backend and review page, so `git push` can bring them up itself."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from offside import config

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
LOG_DIR = Path(tempfile.gettempdir()) / "offside-demo"
PIDS_FILE = LOG_DIR / "pids.json"
STARTUP_TIMEOUT_SECONDS = float(os.environ.get("OFFSIDE_STARTUP_TIMEOUT", "40"))


def find_root() -> Path | None:
    """The Offside checkout that holds the backend and frontend, or None if it can't be found."""
    candidates = []
    if os.environ.get("OFFSIDE_HOME"):
        candidates.append(Path(os.environ["OFFSIDE_HOME"]))
    candidates.append(Path(__file__).resolve().parents[2])  # cli/offside/services.py -> repo root
    for root in candidates:
        if (root / "backend" / "app" / "main.py").exists() and (root / "frontend" / "package.json").exists():
            return root
    return None


def _local_port(url: str) -> int | None:
    parsed = urlparse(url)
    if parsed.hostname not in LOCAL_HOSTS:
        return None
    return parsed.port or (443 if parsed.scheme == "https" else 80)


def autostart_blocker() -> str | None:
    """Why Offside can't start itself here, or None if it can."""
    if os.environ.get("OFFSIDE_AUTOSTART", "1") == "0":
        return "auto-start is turned off (OFFSIDE_AUTOSTART=0)"
    if _local_port(config.BACKEND_URL) is None or _local_port(config.FRONTEND_URL) is None:
        return "the backend and review page are not on this machine, so they can't be started from here"
    root = find_root()
    if root is None:
        return "the Offside checkout was not found (set OFFSIDE_HOME to its path)"
    if not (root / "backend" / ".venv" / "bin" / "python").exists():
        return f"the backend is not set up ({root}/backend/.venv is missing)"
    if not (root / "frontend" / "node_modules" / ".bin" / "vite").exists():
        return f"the frontend is not set up ({root}/frontend/node_modules is missing; run npm install)"
    if shutil.which("node") is None:
        return "node is not on PATH"
    return None


def _healthy(url: str) -> bool:
    try:
        return httpx.get(url, timeout=2.0, follow_redirects=True).status_code < 500
    except (httpx.HTTPError, OSError):
        return False


def _spawn(name: str, command: list[str], cwd: Path, env: dict[str, str]) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = open(LOG_DIR / f"{name}.log", "ab")
    # Detached, with every stream redirected, so git is not left waiting on this process after the push.
    proc = subprocess.Popen(
        command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True
    )
    return proc.pid


def _remember(pids: dict[str, int]) -> None:
    known: dict[str, int] = {}
    try:
        known = json.loads(PIDS_FILE.read_text())
    except (OSError, ValueError):
        pass
    known.update(pids)
    PIDS_FILE.write_text(json.dumps(known))


def start(backend_ok: bool, frontend_ok: bool, say=print) -> str | None:
    """Start whichever of the two is missing and wait until both answer. Returns None on success,
    otherwise a short reason it failed."""
    root = find_root()
    blocker = autostart_blocker()
    if blocker or root is None:
        return f"Offside can't start itself: {blocker}."

    backend_port, frontend_port = _local_port(config.BACKEND_URL), _local_port(config.FRONTEND_URL)
    pids: dict[str, int] = {}
    if not backend_ok:
        say(f"  starting the backend on port {backend_port}...")
        env = {**os.environ, "OFFSIDE_FRONTEND_ORIGIN": config.FRONTEND_URL}
        pids["backend"] = _spawn(
            "backend",
            [str(root / "backend" / ".venv" / "bin" / "python"), "-m", "uvicorn", "app.main:app", "--port", str(backend_port)],
            root / "backend",
            env,
        )
    if not frontend_ok:
        say(f"  starting the review page on port {frontend_port}...")
        env = {**os.environ, "VITE_BACKEND_URL": config.BACKEND_URL}
        pids["frontend"] = _spawn(
            "frontend",
            [str(root / "frontend" / "node_modules" / ".bin" / "vite"), "--port", str(frontend_port), "--strictPort"],
            root / "frontend",
            env,
        )
    _remember(pids)

    deadline = time.time() + STARTUP_TIMEOUT_SECONDS
    while time.time() < deadline:
        if _healthy(f"{config.BACKEND_URL}/health") and _healthy(config.FRONTEND_URL):
            return None
        time.sleep(0.4)
    return f"Offside did not come up within {int(STARTUP_TIMEOUT_SECONDS)} seconds. Logs are in {LOG_DIR}."


def stop() -> list[str]:
    """Stop the services that `start` launched. Returns the names that were stopped."""
    try:
        pids = json.loads(PIDS_FILE.read_text())
    except (OSError, ValueError):
        return []
    stopped = []
    for name, pid in pids.items():
        try:
            os.killpg(pid, 15)  # each service is its own session/process group
            stopped.append(name)
        except (ProcessLookupError, PermissionError):
            pass
    PIDS_FILE.unlink(missing_ok=True)
    return stopped
