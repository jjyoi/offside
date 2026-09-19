from __future__ import annotations

import stat
import subprocess
from pathlib import Path

HOOK_SCRIPT = """#!/bin/sh
# Installed by `offside install`. Do not edit by hand.
offside pre-push "$@"
exit $?
"""


def _run(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    return result.stdout.strip()


def install_hook() -> str:
    """Install the pre-push hook into the current repo's hooks directory.

    Respects a configured core.hooksPath if the repo already uses one;
    otherwise installs directly into .git/hooks.
    """
    hooks_path = _run(["git", "config", "core.hooksPath"])
    if hooks_path:
        hooks_dir = Path(hooks_path)
        if not hooks_dir.is_absolute():
            repo_root = Path(_run(["git", "rev-parse", "--show-toplevel"]))
            hooks_dir = repo_root / hooks_dir
    else:
        git_dir = Path(_run(["git", "rev-parse", "--git-dir"]))
        hooks_dir = git_dir / "hooks"

    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-push"

    if hook_path.exists() and "Installed by `offside install`" not in hook_path.read_text():
        backup = hook_path.with_suffix(".bak")
        hook_path.rename(backup)
        print(f"Existing pre-push hook backed up to {backup}")

    hook_path.write_text(HOOK_SCRIPT)
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    return str(hook_path)
