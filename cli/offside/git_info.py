from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

ZERO_SHA = "0" * 40


@dataclass
class PushRange:
    local_ref: str
    local_sha: str
    remote_ref: str
    remote_sha: str | None  # None when pushing a new branch with no upstream history
    branch: str
    diff: str
    commits: list[str]


def _run(args: list[str], cwd: str | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    return result.stdout.strip()


def repo_root(cwd: str | None = None) -> str:
    root = _run(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    return root or "."


def current_repo_slug(cwd: str | None = None) -> str:
    url = _run(["git", "remote", "get-url", "origin"], cwd=cwd)
    if not url:
        return repo_root(cwd=cwd).split("/")[-1]
    name = url.rstrip("/").rstrip(".git")
    return name.split("/")[-1].split(":")[-1]


def merge_base_or_root(local_sha: str, cwd: str | None = None) -> str:
    """Find a sensible base to diff against when there's no remote SHA (new branch)."""
    for base_candidate in ("origin/main", "origin/master", "main", "master"):
        base = _run(["git", "rev-parse", "--verify", base_candidate], cwd=cwd)
        if base:
            merge_base = _run(["git", "merge-base", base, local_sha], cwd=cwd)
            if merge_base:
                return merge_base
    # No known base branch — diff against the empty tree (full content of new branch).
    return _run(["git", "hash-object", "-t", "tree", "/dev/null"], cwd=cwd)


def read_stdin_refs() -> list[tuple[str, str, str, str]]:
    """Pre-push hook stdin format: <local ref> <local sha1> <remote ref> <remote sha1>, one per line."""
    lines = sys.stdin.read().strip().splitlines()
    refs = []
    for line in lines:
        parts = line.split()
        if len(parts) == 4:
            refs.append(tuple(parts))
    return refs


def build_push_range(
    local_ref: str, local_sha: str, remote_ref: str, remote_sha: str, cwd: str | None = None
) -> PushRange:
    branch = local_ref.split("/")[-1] if local_ref else "unknown"

    if local_sha == ZERO_SHA:
        # Deleting a branch — nothing to review.
        return PushRange(local_ref, local_sha, remote_ref, None, branch, diff="", commits=[])

    if remote_sha == ZERO_SHA or not remote_sha:
        base = merge_base_or_root(local_sha, cwd=cwd)
        diff = _run(["git", "diff", f"{base}..{local_sha}"], cwd=cwd)
        commits_raw = _run(["git", "log", f"{base}..{local_sha}", "--oneline"], cwd=cwd)
        remote_sha_out = None
    else:
        diff = _run(["git", "diff", f"{remote_sha}..{local_sha}"], cwd=cwd)
        commits_raw = _run(["git", "log", f"{remote_sha}..{local_sha}", "--oneline"], cwd=cwd)
        remote_sha_out = remote_sha

    commits = [c for c in commits_raw.splitlines() if c.strip()]
    return PushRange(local_ref, local_sha, remote_ref, remote_sha_out, branch, diff=diff, commits=commits)
