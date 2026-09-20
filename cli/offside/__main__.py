from __future__ import annotations

import argparse
import subprocess
import sys
import time
import webbrowser

import httpx

from offside import config, git_info, prefs
from offside.hook import install_hook


def main() -> None:
    parser = argparse.ArgumentParser(prog="offside")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("install", help="Install the pre-push hook into the current repo")

    config_cmd = subparsers.add_parser("config", help="View or change Offside settings")
    config_cmd.add_argument("key", nargs="?", help="Setting name (e.g. level)")
    config_cmd.add_argument("value", nargs="?", help="New value; omit to show the current one")

    pre_push = subparsers.add_parser("pre-push", help="Invoked by the git pre-push hook")
    pre_push.add_argument("remote_name", nargs="?", default="")
    pre_push.add_argument("remote_url", nargs="?", default="")

    args = parser.parse_args()

    if args.command == "install":
        cmd_install()
    elif args.command == "config":
        sys.exit(cmd_config(args.key, args.value))
    elif args.command == "pre-push":
        cmd_pre_push()


LEVEL_CHOICES = {
    "1": ("intern", "full walkthrough, concepts explained"),
    "2": ("mid", "what's wrong and why it matters"),
    "3": ("staff", "one terse line"),
}


def prompt_for_level(input_fn=None) -> str:
    """Ask which explanation level the user wants. Empty or invalid input keeps the default."""
    input_fn = input_fn or input
    print("How much explanation do you want?")
    for key, (name, blurb) in LEVEL_CHOICES.items():
        print(f"  {key}) {name}: {blurb}")
    default = prefs.DEFAULTS["level"]
    try:
        answer = input_fn(f"Choose 1-3 [{default}]: ").strip().lower()
    except EOFError:
        return default
    if answer in LEVEL_CHOICES:
        return LEVEL_CHOICES[answer][0]
    if answer in prefs.LEVELS:
        return answer
    return default


def cmd_install() -> None:
    path = install_hook()
    print(f"Offside pre-push hook installed at {path}")

    # Only ask once per person, and only when someone is there to answer.
    if not prefs.is_set("level") and sys.stdin.isatty():
        level = prompt_for_level()
        prefs.set_value("level", level)
        print(f"Explanation level set to {level}. Change it any time with `offside config level <intern|mid|staff>`.")


def cmd_config(key: str | None, value: str | None) -> int:
    if key is None:
        for k, v in prefs.load().items():
            print(f"{k} = {v}")
        return 0
    try:
        if value is None:
            print(prefs.get(key))
        else:
            prefs.set_value(key, value)
            print(f"{key} = {value}")
    except (KeyError, ValueError) as exc:
        print(f"offside: {exc if isinstance(exc, ValueError) else f'Unknown setting {key!r}'}", file=sys.stderr)
        return 2
    return 0


def cmd_pre_push() -> None:
    refs = git_info.read_stdin_refs()

    if not refs:
        print("Offside: no refs to push, allowing.")
        sys.exit(0)

    if not prefs.is_set("level"):
        print("Offside: explanation level is mid. Change it with `offside config level <intern|mid|staff>`.")

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
                    "level": prefs.get("level"),
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
    findings = session.get("findings", [])
    if blocked:
        print(f"PUSH BLOCKED — HP {hp}")
        for f in findings:
            if f["severity"] == "red" and f.get("fix_decision") != "accepted":
                print(f"  RED CARD {f['file']}:{f['start_line']} — {f['explanation']}")
            elif f.get("fix_decision") == "declined":
                print(f"  CONCEDED, NO FIX AGREED {f['file']}:{f['start_line']}")
    else:
        print(f"PUSH ALLOWED — HP {hp}")

    accepted = [f for f in findings if f.get("fix_decision") == "accepted" and f.get("suggested_fix")]
    if accepted:
        print("Fixes you accepted (not part of this push, apply them next):")
        for f in accepted:
            print(f"  {f['file']}:{f['start_line']} — {f['suggested_fix']}")


def _fail_open(message: str) -> int:
    if config.FAIL_OPEN:
        print(f"Offside: {message} Failing open — play on.")
        return 0
    print(f"Offside: {message} Failing closed — push blocked.")
    return 1


if __name__ == "__main__":
    main()
