from __future__ import annotations

import re
import subprocess
from pathlib import Path

from app.models import Evidence, EvidenceType

"""Deterministic, allowlisted evidence-gathering tools.

Per spec section 22: "Never let a model directly execute arbitrary shell
commands. All tool execution must pass through an explicit allowlist."
These functions are the only allowlisted entry points into the repo/git;
the model never gets raw shell access.
"""

_ALLOWED_GIT_SUBCOMMANDS = {"log", "blame", "show", "grep"}


def _run_git(repo_path: str, args: list[str], timeout: float = 5.0) -> str:
    if not args or args[0] not in _ALLOWED_GIT_SUBCOMMANDS:
        raise ValueError(f"git subcommand not allowlisted: {args[0] if args else '<empty>'}")
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def git_history_evidence(repo_path: str, file: str, start_line: int, end_line: int) -> Evidence | None:
    """Why was this region last touched? Uses git log -L for line-range history."""
    if not repo_path or not Path(repo_path, file).exists():
        return None
    output = _run_git(
        repo_path,
        ["log", f"-L{start_line},{end_line}:{file}", "-1", "--format=%h %s (%an, %ar)"],
        timeout=5.0,
    )
    if not output:
        return None
    header = output.splitlines()[0] if output.splitlines() else output
    return Evidence(
        type=EvidenceType.git_history,
        summary=f"Last change to this region: {header}",
        source_ref=f"{file}:{start_line}-{end_line}",
        strength=0.5,
    )


def repo_context_evidence(repo_path: str, file: str, pattern: str) -> Evidence | None:
    """Search the repo for sibling call sites of a pattern to establish convention."""
    if not repo_path:
        return None
    output = _run_git(repo_path, ["grep", "-n", "-i", "--", pattern], timeout=5.0)
    if not output:
        return None
    lines = [ln for ln in output.splitlines() if ln.strip()]
    count = len(lines)
    sample = lines[0] if lines else ""
    return Evidence(
        type=EvidenceType.repo_context,
        summary=f"Found {count} comparable usage(s) of '{pattern}' elsewhere in the repo.",
        source_ref=sample.split(":")[0] if sample else None,
        strength=min(0.4 + count * 0.05, 0.9),
    )


def caller_evidence(repo_path: str, symbol: str) -> Evidence | None:
    """Search for call sites of a function/symbol to check what callers actually enforce."""
    if not repo_path or not symbol:
        return None
    output = _run_git(repo_path, ["grep", "-n", "-w", symbol], timeout=5.0)
    if not output:
        return None
    lines = [ln for ln in output.splitlines() if ln.strip()]
    return Evidence(
        type=EvidenceType.repo_context,
        summary=f"Found {len(lines)} reference(s) to '{symbol}' in the repository.",
        source_ref=lines[0].split(":")[0] if lines else None,
        strength=min(0.4 + len(lines) * 0.05, 0.85),
    )


_TIMEOUT_RE = re.compile(r"timeout\s*[:=]?\s*(\d+)|(\d+)[\s-]*(?:second|sec|ms|millisecond)s?\s*timeout", re.IGNORECASE)


def claim_mentions_timeout(text: str) -> int | None:
    match = _TIMEOUT_RE.search(text)
    if not match:
        return None
    return int(match.group(1) or match.group(2))


def lint_evidence(diff: str) -> Evidence | None:
    """Cheap deterministic lint-style pass over the diff text (no external linter dependency)."""
    added = [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    issues = []
    for ln in added:
        if len(ln) > 120:
            issues.append("line exceeds 120 chars")
        if "\t " in ln or " \t" in ln:
            issues.append("mixed tabs/spaces")
    if not issues:
        return Evidence(
            type=EvidenceType.lint,
            summary="No lint issues found in added lines.",
            strength=0.3,
        )
    return Evidence(
        type=EvidenceType.lint,
        summary=f"Lint issues: {', '.join(sorted(set(issues)))}.",
        strength=0.4,
    )
