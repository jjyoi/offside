from __future__ import annotations

import json
import os
from pathlib import Path

LEVELS = ("intern", "mid", "staff", "messi", "ronaldo", "son")
DEFAULTS: dict[str, str] = {"level": "mid"}


def config_path() -> Path:
    base = os.environ.get("OFFSIDE_CONFIG_DIR")
    if base:
        return Path(base) / "config.json"
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(xdg) / "offside" / "config.json"


def load() -> dict[str, str]:
    """Saved preferences merged over defaults. A missing or corrupt file yields defaults."""
    prefs = dict(DEFAULTS)
    try:
        data = json.loads(config_path().read_text())
    except (OSError, ValueError):
        return prefs
    if isinstance(data, dict):
        prefs.update({k: v for k, v in data.items() if k in DEFAULTS and isinstance(v, str)})
    return prefs


def is_set(key: str) -> bool:
    """True if the user has explicitly saved this key (as opposed to falling back to the default)."""
    try:
        data = json.loads(config_path().read_text())
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and key in data


def get(key: str) -> str:
    return load()[key]


def set_value(key: str, value: str) -> None:
    if key not in DEFAULTS:
        raise ValueError(f"Unknown setting '{key}'. Known settings: {', '.join(DEFAULTS)}")
    if key == "level" and value not in LEVELS:
        raise ValueError(f"Invalid level '{value}'. Choose one of: {', '.join(LEVELS)}")

    path = config_path()
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
