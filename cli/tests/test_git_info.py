import subprocess

import pytest

from offside import git_info


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    return path


@pytest.fixture
def repo(tmp_path):
    return _init_repo(tmp_path / "repo")


def _commit(repo, filename, content, message):
    (repo / filename).write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_build_push_range_diffs_against_remote_sha(repo):
    sha1 = _commit(repo, "a.txt", "one\n", "first")
    sha2 = _commit(repo, "a.txt", "two\n", "second")

    pr = git_info.build_push_range("refs/heads/main", sha2, "refs/heads/main", sha1, cwd=str(repo))

    assert pr.remote_sha == sha1
    assert pr.local_sha == sha2
    assert "-one" in pr.diff
    assert "+two" in pr.diff
    assert len(pr.commits) == 1
    assert pr.author == "Test"


def test_build_push_range_new_branch_diffs_against_merge_base(repo):
    _commit(repo, "a.txt", "one\n", "first")
    _git(repo, "branch", "-m", "main")
    _git(repo, "checkout", "-q", "-b", "feature")
    sha_feature = _commit(repo, "b.txt", "new file\n", "add feature file")

    pr = git_info.build_push_range(
        "refs/heads/feature", sha_feature, "refs/heads/feature", git_info.ZERO_SHA, cwd=str(repo)
    )

    assert pr.remote_sha is None
    assert "+new file" in pr.diff
    assert pr.branch == "feature"


def test_build_push_range_branch_deletion_has_no_diff(repo):
    sha1 = _commit(repo, "a.txt", "one\n", "first")

    pr = git_info.build_push_range(
        "refs/heads/doomed", git_info.ZERO_SHA, "refs/heads/doomed", sha1, cwd=str(repo)
    )

    assert pr.diff == ""
    assert pr.commits == []
