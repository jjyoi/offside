"""Exercises the real installed shell hook in throwaway git repos: chaining, stdin, and failure policy."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from offside import hook

ZERO = "0" * 40
CLOSED_PORT = "http://127.0.0.1:9"  # nothing listens here, so the backend looks down


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@t")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n")
    git(tmp_path, "add", "a.py")
    git(tmp_path, "commit", "-qm", "base")
    # A feature branch with a change on top of main, so the push has a real diff to review.
    git(tmp_path, "checkout", "-q", "-b", "feature")
    (tmp_path / "a.py").write_text("x = 1\ny = 2\n")
    git(tmp_path, "commit", "-qam", "change")
    return tmp_path


def refs_line(repo):
    """What git feeds a pre-push hook for a brand-new branch: <local ref> <sha> <remote ref> <zeros>."""
    return f"refs/heads/feature {git(repo, 'rev-parse', 'HEAD')} refs/heads/feature {ZERO}\n"


def run_hook(repo, extra_env=None, hooks_dir=None):
    hook_path = (Path(hooks_dir) if hooks_dir else Path(repo) / ".git" / "hooks") / "pre-push"
    env = {**os.environ, "OFFSIDE_BACKEND_URL": CLOSED_PORT, "OFFSIDE_FRONTEND_URL": CLOSED_PORT, "OFFSIDE_AUTOSTART": "0", **(extra_env or {})}
    return subprocess.run(["sh", str(hook_path), "origin", "url"], cwd=repo, input=refs_line(repo), text=True, capture_output=True, env=env)


def write_prev_hook(repo, body):
    path = Path(repo) / ".git" / "hooks" / "pre-push"
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)


def test_install_records_absolute_interpreter_and_needs_no_path(repo, monkeypatch):
    result = hook.install_hook(cwd=str(repo))
    script = Path(result.path).read_text()
    assert result.mode == "local" and not result.chained
    assert sys.executable in script
    # Runs with a PATH that cannot find `offside`: the recorded interpreter is used instead.
    out = run_hook(repo, {"PATH": "/usr/bin:/bin"})
    assert "OFFSIDE IS NOT RUNNING" in out.stdout  # reached the CLI, which reported the dead backend


def test_backend_down_is_loud_and_fails_open_by_default(repo):
    hook.install_hook(cwd=str(repo))
    out = run_hook(repo)
    assert out.returncode == 0
    assert "NOT reviewed" in out.stdout and "offside up" in out.stdout and "UNREVIEWED" in out.stdout


def test_backend_down_blocks_when_fail_open_disabled(repo):
    hook.install_hook(cwd=str(repo))
    out = run_hook(repo, {"OFFSIDE_FAIL_OPEN": "0"})
    assert out.returncode == 1
    assert "Failing closed" in out.stdout


def test_missing_cli_follows_the_same_policy_as_a_dead_backend(repo):
    result = hook.install_hook(cwd=str(repo))
    script = Path(result.path)
    script.write_text(script.read_text().replace(sys.executable, "/nonexistent/python"))
    env = {"PATH": "/usr/bin:/bin"}
    open_out = run_hook(repo, env)
    assert open_out.returncode == 0 and "CANNOT RUN" in open_out.stderr
    closed_out = run_hook(repo, {**env, "OFFSIDE_FAIL_OPEN": "0"})
    assert closed_out.returncode == 1


def test_existing_hook_is_chained_not_replaced(repo):
    seen = Path(repo) / "seen.txt"
    write_prev_hook(repo, f'cat > "{seen}"\nexit 0\n')
    result = hook.install_hook(cwd=str(repo))
    assert result.chained
    assert (Path(repo) / ".git" / "hooks" / f"pre-push{hook.CHAINED_SUFFIX}").exists()
    out = run_hook(repo)
    assert seen.read_text() == refs_line(repo)  # the old hook still ran, with the same refs on stdin
    assert "OFFSIDE IS NOT RUNNING" in out.stdout  # and Offside ran after it


def test_failing_existing_hook_stops_the_push_before_offside_runs(repo):
    write_prev_hook(repo, "echo 'lint failed' >&2\nexit 7\n")
    hook.install_hook(cwd=str(repo))
    out = run_hook(repo)
    assert out.returncode == 7
    assert "lint failed" in out.stderr
    assert "OFFSIDE" not in out.stdout


def test_reinstalling_is_idempotent_and_does_not_chain_itself(repo):
    write_prev_hook(repo, "exit 0\n")
    hook.install_hook(cwd=str(repo))
    first = (Path(repo) / ".git" / "hooks" / "pre-push").read_text()
    result = hook.install_hook(cwd=str(repo))
    assert result.chained
    assert (Path(repo) / ".git" / "hooks" / "pre-push").read_text() == first
    prev = Path(repo) / ".git" / "hooks" / f"pre-push{hook.CHAINED_SUFFIX}"
    assert hook.MARKER not in prev.read_text()


def test_shared_hook_is_committed_and_new_clones_only_need_install(repo):
    result = hook.install_hook(shared=True, cwd=str(repo))
    assert result.mode == "shared"
    assert Path(result.path) == Path(repo) / ".githooks" / "pre-push"
    assert git(repo, "config", "core.hooksPath") == ".githooks"
    git(repo, "add", ".githooks")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "add offside hook")

    clone = repo.parent / "clone"
    subprocess.run(["git", "clone", "-q", str(repo), str(clone)], check=True, capture_output=True)
    assert subprocess.run(["git", "config", "core.hooksPath"], cwd=clone, capture_output=True, text=True).stdout.strip() == ""
    again = hook.install_hook(cwd=str(clone))  # what a teammate runs once after cloning
    assert again.mode == "shared-existing"
    assert git(clone, "config", "core.hooksPath") == ".githooks"


def test_shared_hook_without_offside_installed_warns_and_follows_policy(repo):
    hook.install_hook(shared=True, cwd=str(repo))
    out = run_hook(repo, {"PATH": "/usr/bin:/bin"}, hooks_dir=Path(repo) / ".githooks")
    assert out.returncode == 0 and "not installed on this machine" in out.stderr
    closed = run_hook(repo, {"PATH": "/usr/bin:/bin", "OFFSIDE_FAIL_OPEN": "0"}, hooks_dir=Path(repo) / ".githooks")
    assert closed.returncode == 1


def test_not_a_git_repo_is_reported(tmp_path):
    with pytest.raises(RuntimeError):
        hook.install_hook(cwd=str(tmp_path))
