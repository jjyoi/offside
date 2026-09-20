import os
import subprocess
import sys
import time

import pytest

from offside import __main__ as cli
from offside import config, services


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def test_finds_the_offside_checkout():
    root = services.find_root()
    assert root is not None and (root / "backend" / "app" / "main.py").exists()


def test_autostart_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("OFFSIDE_AUTOSTART", "0")
    assert "turned off" in services.autostart_blocker()


def test_never_tries_to_start_a_backend_that_is_not_on_this_machine(monkeypatch):
    monkeypatch.setattr(config, "BACKEND_URL", "https://offside.example.com")
    assert "not on this machine" in services.autostart_blocker()
    assert "can't start itself" in services.start(False, False)


def test_reports_a_missing_setup_instead_of_failing_mysteriously(monkeypatch, tmp_path):
    (tmp_path / "backend" / "app").mkdir(parents=True)
    (tmp_path / "backend" / "app" / "main.py").write_text("")
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / "package.json").write_text("{}")
    monkeypatch.setenv("OFFSIDE_HOME", str(tmp_path))
    monkeypatch.setattr(services, "find_root", lambda: tmp_path)
    assert "backend is not set up" in services.autostart_blocker()


def test_only_the_missing_service_is_started(monkeypatch):
    started = []
    monkeypatch.setattr(services, "autostart_blocker", lambda: None)
    monkeypatch.setattr(services, "_spawn", lambda name, *a, **k: started.append(name) or 4242)
    monkeypatch.setattr(services, "_remember", lambda pids: None)
    monkeypatch.setattr(services, "_healthy", lambda url: True)
    assert services.start(backend_ok=True, frontend_ok=False, say=lambda *_: None) is None
    assert started == ["frontend"]
    started.clear()
    assert services.start(backend_ok=False, frontend_ok=True, say=lambda *_: None) is None
    assert started == ["backend"]


def test_gives_up_with_a_reason_and_log_location_when_it_never_comes_up(monkeypatch):
    monkeypatch.setattr(services, "autostart_blocker", lambda: None)
    monkeypatch.setattr(services, "_spawn", lambda *a, **k: 4242)
    monkeypatch.setattr(services, "_remember", lambda pids: None)
    monkeypatch.setattr(services, "_healthy", lambda url: False)
    monkeypatch.setattr(services, "STARTUP_TIMEOUT_SECONDS", 0.5)
    reason = services.start(False, False, say=lambda *_: None)
    assert "did not come up" in reason and str(services.LOG_DIR) in reason


def test_down_stops_only_what_was_started_and_forgets_it(monkeypatch, tmp_path):
    monkeypatch.setattr(services, "LOG_DIR", tmp_path)
    monkeypatch.setattr(services, "PIDS_FILE", tmp_path / "pids.json")
    proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
    services._remember({"backend": proc.pid})
    assert services.stop() == ["backend"]
    proc.wait(timeout=5)
    assert proc.returncode is not None
    assert not (tmp_path / "pids.json").exists()
    assert services.stop() == []  # nothing left to stop


def test_connect_makes_a_plain_push_work_on_a_new_branch(tmp_path, monkeypatch, capsys):
    git(tmp_path, "init", "-q")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert cli.cmd_connect() == 0
    assert git(tmp_path, "config", "--local", "push.autoSetupRemote") == "true"
    assert (tmp_path / ".git" / "hooks" / "pre-push").exists()
    assert "Connected" in capsys.readouterr().out


def test_a_plain_git_push_creates_the_upstream_after_connect(tmp_path, monkeypatch):
    """The real failure this fixes: `git push` on a new branch used to stop with 'no upstream configured'."""
    remote, work = tmp_path / "remote.git", tmp_path / "work"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(tmp_path, "clone", "-q", str(remote), str(work))
    git(work, "config", "user.email", "t@t")
    git(work, "config", "user.name", "t")
    (work / "a.txt").write_text("x")
    git(work, "add", ".")
    git(work, "commit", "-qm", "one")
    git(work, "checkout", "-q", "-b", "feature")

    before = subprocess.run(["git", "push"], cwd=work, capture_output=True, text=True)
    assert before.returncode != 0 and "no upstream branch" in before.stderr

    git(work, "config", "--local", "push.autoSetupRemote", "true")  # what `offside connect` does
    after = subprocess.run(["git", "push"], cwd=work, capture_output=True, text=True)
    assert after.returncode == 0
    assert git(work, "rev-parse", "--abbrev-ref", "feature@{upstream}") == "origin/feature"
