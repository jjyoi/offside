from __future__ import annotations

import shlex
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MARKER = "Installed by `offside install`"
SHARED_DIR = ".githooks"
CHAINED_SUFFIX = ".offside-prev"

# Shared shell prologue: git feeds the pushed refs on stdin exactly once, but both a chained hook and
# Offside need to read them, so keep a copy. `{chain}` runs any hook that was here before Offside.
_PROLOGUE = """#!/bin/sh
# {marker}. Re-run `offside install` to update; do not edit by hand.
refs_file=$(mktemp "${{TMPDIR:-/tmp}}/offside-refs.XXXXXX") || exit 1
trap 'rm -f "$refs_file"' EXIT
cat > "$refs_file"
{chain}"""

_CHAIN = """
# A pre-push hook existed before Offside was installed; keep running it, and stop if it fails.
prev="$(dirname "$0")/pre-push{suffix}"
if [ -x "$prev" ]; then
  "$prev" "$@" < "$refs_file" || exit $?
fi
"""

# If Offside itself can't run, follow the same policy as "backend unreachable" so a missing binary
# and a dead backend behave alike: fail open unless OFFSIDE_FAIL_OPEN=0.
_UNAVAILABLE = """
cat >&2 <<'MSG'

==============================================================
  OFFSIDE CANNOT RUN: this push was NOT reviewed
  {reason}
==============================================================

MSG
if [ "${{OFFSIDE_FAIL_OPEN:-1}}" = "0" ]; then
  echo "Offside: failing closed, push blocked." >&2
  exit 1
fi
echo "Offside: failing open, push continues. Set OFFSIDE_FAIL_OPEN=0 to block instead." >&2
exit 0
"""

_LOCAL_RUN = """
# Absolute interpreter recorded at install time, so the hook does not depend on PATH.
python=@PYTHON@
if [ -x "$python" ] && "$python" -c "import offside" >/dev/null 2>&1; then
  "$python" -m offside pre-push "$@" < "$refs_file"
  exit $?
fi
if command -v offside >/dev/null 2>&1; then
  offside pre-push "$@" < "$refs_file"
  exit $?
fi
""" + _UNAVAILABLE.format(reason="The Offside CLI moved or was removed. Run `offside install` again.")

_SHARED_RUN = """
# Committed, shared hook: finds Offside on this machine (set OFFSIDE_BIN to point at it).
bin="${OFFSIDE_BIN:-offside}"
if command -v "$bin" >/dev/null 2>&1; then
  "$bin" pre-push "$@" < "$refs_file"
  exit $?
fi
""" + _UNAVAILABLE.format(reason="Offside is not installed on this machine. Install the CLI, then run `offside install`.")


def _run(args: list[str], cwd: str | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    return result.stdout.strip()


@dataclass
class InstallResult:
    path: str
    mode: str  # "local", "shared" or "shared-existing"
    chained: bool  # an earlier pre-push hook is still run before Offside


def repo_root(cwd: str | None = None) -> Path:
    root = _run(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    if not root:
        raise RuntimeError("Not inside a git repository.")
    return Path(root)


def hooks_dir(cwd: str | None = None) -> Path:
    """Where git will look for hooks: core.hooksPath if set, otherwise the repo's hooks directory."""
    root = repo_root(cwd)
    configured = _run(["git", "config", "core.hooksPath"], cwd=cwd)
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else root / path
    git_path = _run(["git", "rev-parse", "--git-path", "hooks"], cwd=cwd)
    path = Path(git_path)
    return path if path.is_absolute() else Path(cwd or ".").resolve() / path


def is_offside_hook(path: Path) -> bool:
    try:
        return MARKER in path.read_text()
    except OSError:
        return False


def _make_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _write_hook(hooks: Path, run_block: str) -> tuple[Path, bool]:
    """Write the Offside hook into `hooks`, chaining any hook that was already there."""
    hooks.mkdir(parents=True, exist_ok=True)
    hook_path = hooks / "pre-push"
    chained_path = hooks / f"pre-push{CHAINED_SUFFIX}"

    if hook_path.exists() and not is_offside_hook(hook_path):
        hook_path.rename(chained_path)  # keep it, and run it first from now on

    chained = chained_path.exists()
    chain = _CHAIN.format(suffix=CHAINED_SUFFIX) if chained else ""
    hook_path.write_text(_PROLOGUE.format(marker=MARKER, chain=chain) + run_block)
    _make_executable(hook_path)
    return hook_path, chained


def install_hook(shared: bool = False, cwd: str | None = None) -> InstallResult:
    """Install the pre-push hook for the current repo.

    Default: write a hook into the repo's hooks directory that records this interpreter's absolute
    path. `shared=True`: write it to a committed `.githooks/` folder and point core.hooksPath at it,
    so teammates only need `offside install` once per clone. If that folder already holds an Offside
    hook (someone committed it), just point git at it.
    """
    root = repo_root(cwd)
    shared_hook = root / SHARED_DIR / "pre-push"

    if shared:
        path, chained = _write_hook(root / SHARED_DIR, _SHARED_RUN)
        _run(["git", "config", "core.hooksPath", SHARED_DIR], cwd=cwd)
        return InstallResult(str(path), "shared", chained)

    if is_offside_hook(shared_hook):
        _run(["git", "config", "core.hooksPath", SHARED_DIR], cwd=cwd)
        chained = (root / SHARED_DIR / f"pre-push{CHAINED_SUFFIX}").exists()
        return InstallResult(str(shared_hook), "shared-existing", chained)

    path, chained = _write_hook(hooks_dir(cwd), _LOCAL_RUN.replace("@PYTHON@", shlex.quote(sys.executable)))
    return InstallResult(str(path), "local", chained)
