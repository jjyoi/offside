from __future__ import annotations

import argparse
import subprocess
import sys
import time
import webbrowser

import httpx

from offside import config, git_info
from offside.hook import install_hook


def main() -> None:
    parser = argparse.ArgumentParser(prog="offside")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("install", help="Install the pre-push hook into the current repo")

    pre_push = subparsers.add_parser("pre-push", help="Invoked by the git pre-push hook")
    pre_push.add_argument("remote_name", nargs="?", default="")
    pre_push.add_argument("remote_url", nargs="?", default="")

    args = parser.parse_args()

    if args.command == "install":
        cmd_install()
    elif args.command == "pre-push":
        cmd_pre_push()


def cmd_install() -> None:
    path = install_hook()
    print(f"Offside pre-push hook installed at {path}")


def cmd_pre_push() -> None:
    refs = git_info.read_stdin_refs()

    if not refs:
        print("Offside: no refs to push, allowing.")
        sys.exit(0)

    repo_root = git_info.repo_root()
    repo_slug = git_info.current_repo_slug()

    exit_code = 0
    for local_ref, local_sha, remote_ref, remote_sha in refs:
        push_range = git_info.build_push_range(local_ref, local_sha, remote_ref, remote_sha, cwd=repo_root)

        if not push_range.diff:
            print(f"Offside: no diff to review for {push_range.branch} (branch deletion or empty push), allowing.")
            continue

        code = review_one(repo_slug, repo_root, push_range)
        exit_code = exit_code or code

    sys.exit(exit_code)


def review_one(repo_slug: str, repo_root: str, push_range: git_info.PushRange) -> int:
    print("Possible offence detected. Checking VAR...")

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{config.BACKEND_URL}/api/reviews",
                json={
                    "repo": repo_slug,
                    "branch": push_range.branch,
                    "local_sha": push_range.local_sha,
                    "remote_sha": push_range.remote_sha,
                    "diff": push_range.diff,
                    "commits": push_range.commits,
                    "repo_path": repo_root,
                    "author": push_range.author,
                },
            )
            resp.raise_for_status()
            body = resp.json()
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        return _fail_open(f"Offside backend unreachable ({exc}).")

    session_id = body["session_id"]
    review_url = body["review_url"]

    print(f"VAR review: {review_url}")
    opened = webbrowser.open(review_url)
    if not opened:
        print(f"Open this URL to continue: {review_url}")

    return wait_for_verdict(session_id, review_url)


def wait_for_verdict(session_id: str, review_url: str) -> int:
    deadline = time.time() + config.WAIT_TIMEOUT_SECONDS
    print("Waiting for VAR decision... (contest in the browser if you disagree)")

    with httpx.Client(timeout=20.0) as client:
        while time.time() < deadline:
            try:
                resp = client.get(f"{config.BACKEND_URL}/api/reviews/{session_id}")
                resp.raise_for_status()
                session = resp.json()
            except (httpx.HTTPError, httpx.TimeoutException):
                time.sleep(1.0)
                continue

            status = session["status"]
            if status == "approved":
                _print_result(session, blocked=False)
                return 0
            if status == "blocked":
                _print_result(session, blocked=True)
                return 1

            time.sleep(1.0)

    return _fail_open("Offside review timed out waiting for a verdict.")


def _print_result(session: dict, blocked: bool) -> None:
    hp = session.get("hp_after", 100)
    if blocked:
        print(f"PUSH BLOCKED — HP {hp}")
        for f in session.get("findings", []):
            if f["severity"] == "red":
                print(f"  RED CARD {f['file']}:{f['start_line']} — {f['explanation']}")
    else:
        print(f"PUSH ALLOWED — HP {hp}")


def _fail_open(message: str) -> int:
    if config.FAIL_OPEN:
        print(f"Offside: {message} Failing open — play on.")
        return 0
    print(f"Offside: {message} Failing closed — push blocked.")
    return 1


if __name__ == "__main__":
    main()
