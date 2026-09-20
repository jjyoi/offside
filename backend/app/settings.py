from __future__ import annotations

import json
import os
from pathlib import Path

from app.models import ExplanationLevel


def config_path() -> Path:
    """Same file the CLI reads and writes (cli/offside/prefs.py), so the two stay in sync."""
    base = os.environ.get("OFFSIDE_CONFIG_DIR")
    if base:
        return Path(base) / "config.json"
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(xdg) / "offside" / "config.json"


def _read() -> dict:
    try:
        data = json.loads(config_path().read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def get_level() -> ExplanationLevel:
    try:
        return ExplanationLevel(_read().get("level", ExplanationLevel.mid.value))
    except ValueError:
        return ExplanationLevel.mid


def set_level(level: ExplanationLevel) -> None:
    data = _read()
    data["level"] = level.value
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
