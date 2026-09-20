from __future__ import annotations

import argparse
import subprocess
import sys
import time
import webbrowser

import httpx

from offside import config, git_info, prefs, services
from offside import hook as hook_mod
from offside.hook import install_hook


def main() -> None:
    parser = argparse.ArgumentParser(prog="offside")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install", help="Install the pre-push hook into the current repo")
    install.add_argument(
        "--shared",
        action="store_true",
        help="Put the hook in a committed .githooks/ folder so teammates only run `offside install` once per clone",
    )

    connect = subparsers.add_parser(
        "connect", help="Connect this repo to Offside: install the hook and make a plain `git push` just work"
    )
    connect.add_argument("--shared", action="store_true", help="Commit the hook in .githooks/ so teammates get it too")

    subparsers.add_parser("up", help="Start the Offside backend and review page")
    subparsers.add_parser("down", help="Stop the backend and review page that Offside started")
    subparsers.add_parser("doctor", help="Check that Offside is ready to review a push from this repo")

    config_cmd = subparsers.add_parser("config", help="View or change Offside settings")
    config_cmd.add_argument("key", nargs="?", help="Setting name (e.g. level)")
    config_cmd.add_argument("value", nargs="?", help="New value; omit to show the current one")

    pre_push = subparsers.add_parser("pre-push", help="Invoked by the git pre-push hook")
    pre_push.add_argument("remote_name", nargs="?", default="")
    pre_push.add_argument("remote_url", nargs="?", default="")

    args = parser.parse_args()

    if args.command == "install":
        cmd_install(shared=args.shared)
    elif args.command == "connect":
        sys.exit(cmd_connect(shared=args.shared))
    elif args.command == "up":
        sys.exit(cmd_up())
    elif args.command == "down":
        sys.exit(cmd_down())
    elif args.command == "doctor":
        sys.exit(cmd_doctor())
    elif args.command == "config":
        sys.exit(cmd_config(args.key, args.value))
    elif args.command == "pre-push":
        cmd_pre_push()


LEVEL_CHOICES = {
    "1": ("intern", "gentler review, full walkthroughs; only serious problems get red cards"),
    "2": ("mid", "balanced review, explains what's wrong and why it matters"),
    "3": ("staff", "strict, design-focused review, one terse line per finding"),
    "4": ("messi", "balanced review, written in Spanish"),
    "5": ("ronaldo", "balanced review, written in Portuguese"),
    "6": ("son", "balanced review, written in Korean"),
}


def prompt_for_level(input_fn=None) -> str:
    """Ask which explanation level the user wants. Empty or invalid input keeps the default."""
    input_fn = input_fn or input
    print("How should Offside review your code? (this sets both how strict it is and how much it explains)")
    for key, (name, blurb) in LEVEL_CHOICES.items():
        print(f"  {key}) {name}: {blurb}")
    default = prefs.DEFAULTS["level"]
    try:
        answer = input_fn(f"Choose 1-6 [{default}]: ").strip().lower()
    except EOFError:
        return default
    if answer in LEVEL_CHOICES:
        return LEVEL_CHOICES[answer][0]
    if answer in prefs.LEVELS:
        return answer
    return default


def cmd_install(shared: bool = False) -> None:
    try:
        result = install_hook(shared=shared)
    except RuntimeError as exc:
        print(f"offside: {exc}", file=sys.stderr)
        sys.exit(2)

    print(f"Offside pre-push hook installed at {result.path}")
    if result.mode == "shared":
        print("It lives in .githooks/ so it can be committed. Teammates run `offside install` once after cloning.")
    elif result.mode == "shared-existing":
        print("This repo already ships an Offside hook in .githooks/, so git now points at it.")
    if result.chained:
        print("Your existing pre-push hook is kept and still runs first.")

    # Only ask once per person, and only when someone is there to answer.
    if not prefs.is_set("level") and sys.stdin.isatty():
        level = prompt_for_level()
        prefs.set_value("level", level)
        print(f"Explanation level set to {level}. Change it any time with `offside config level <intern|mid|staff|messi|ronaldo|son>`.")


def cmd_connect(shared: bool = False) -> int:
    """One step to protect a repo: install the hook and make sure a bare `git push` works."""
    cmd_install(shared=shared)
    # A new branch has no upstream, and plain `git push` would refuse before Offside ever ran.
    subprocess.run(["git", "config", "--local", "push.autoSetupRemote", "true"], check=False)
    print("Connected. From now on, `git push` in this repo opens the Offside review by itself.")
    blocker = services.autostart_blocker()
    if blocker:
        print(f"Note: Offside will not start itself here ({blocker}). Start it with `offside up` or ./demo.sh.")
    else:
        print("If Offside isn't running when you push, it starts itself (stop it later with `offside down`).")
    return 0


def cmd_up() -> int:
    backend_ok, frontend_ok = check_services()
    if not (backend_ok and frontend_ok):
        reason = services.start(backend_ok, frontend_ok)
        if reason:
            print(f"offside: {reason}", file=sys.stderr)
            return 1
    print(f"Offside is running.\n  backend   {config.BACKEND_URL}\n  frontend  {config.FRONTEND_URL}")
    print("Stop it with `offside down`.")
    return 0


def cmd_down() -> int:
    stopped = services.stop()
    print(f"Stopped: {', '.join(stopped)}." if stopped else "Nothing that Offside started is running.")
    return 0


def check_services(timeout: float = 2.0) -> tuple[bool, bool]:
    """Is the backend healthy, and is the review page reachable? Both are needed to finish a review."""

    def reachable(url: str) -> bool:
        try:
            return httpx.get(url, timeout=timeout, follow_redirects=True).status_code < 500
        except (httpx.HTTPError, OSError):
            return False

    return reachable(f"{config.BACKEND_URL}/health"), reachable(config.FRONTEND_URL)


def cmd_doctor() -> int:
    backend_ok, frontend_ok = check_services()
    ok = True

    def line(good: bool, name: str, detail: str) -> None:
        nonlocal ok
        ok = ok and good
        print(f"  {'ok ' if good else 'NO '} {name.ljust(9)} {detail}")

    print("Offside doctor")
    blocker = services.autostart_blocker()

    def service(ok: bool, name: str, url: str, up: str) -> None:
        if ok:
            line(True, name, f"{url} {up}")
        elif blocker is None:
            line(True, name, f"{url} is not running yet. A push will start it.")  # not a problem: it starts itself
        else:
            line(False, name, f"{url} is not responding. Start it with `offside up`.")

    service(backend_ok, "backend", config.BACKEND_URL, "is healthy")
    service(frontend_ok, "frontend", config.FRONTEND_URL, "is reachable")

    try:
        hook_path = hook_mod.hooks_dir() / "pre-push"
        installed = hook_mod.is_offside_hook(hook_path)
        line(installed, "hook", str(hook_path) if installed else "not installed in this repo. Run `offside install`")
    except RuntimeError:
        line(False, "hook", "this is not a git repository")

    line(True, "autostart", "on: a push starts Offside if it is not running" if not blocker else f"off: {blocker}")
    line(True, "level", prefs.get("level"))
    policy = "fail open (push continues if Offside is down)" if config.FAIL_OPEN else "fail closed (push blocked if Offside is down)"
    line(True, "policy", policy + ". Set OFFSIDE_FAIL_OPEN=0 to block.")
    print("Ready." if ok else "Not ready: fix the lines marked NO.")
    return 0 if ok else 1


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

    repo_root = git_info.repo_root()
    repo_slug = git_info.current_repo_slug()

    # Work out what is actually being pushed first, so a branch deletion or empty push never
    # starts (or waits on) the backend just to say there is nothing to review.
    to_review = []
    for local_ref, local_sha, remote_ref, remote_sha in refs:
        push_range = git_info.build_push_range(local_ref, local_sha, remote_ref, remote_sha, cwd=repo_root)
        if not push_range.diff:
            print(f"Offside: no diff to review for {push_range.branch} (branch deletion or empty push), allowing.")
            continue
        to_review.append(push_range)

    if not to_review:
        sys.exit(0)

    if not prefs.is_set("level"):
        print("Offside: explanation level is mid. Change it with `offside config level <intern|mid|staff|messi|ronaldo|son>`.")

    backend_ok, frontend_ok = check_services()
    if not (backend_ok and frontend_ok):
        print("\nOffside is not running. Starting it for this push...")
        reason = services.start(backend_ok, frontend_ok)
        if reason:
            sys.exit(_fail_open(reason))
        print("  ready.\n")

    exit_code = 0
    for push_range in to_review:
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
        if hp <= 0:
            print("  OUT OF HP: with no HP left the push is blocked.")
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
    """Offside can't do its job. Say so loudly, then follow the fail-open/closed policy."""
    verdict = "Failing open, this push will go through UNREVIEWED." if config.FAIL_OPEN else "Failing closed, push blocked."
    bar = "=" * 62
    print(f"\n{bar}\n  OFFSIDE IS NOT RUNNING: this push was NOT reviewed\n  {message}")
    print("  Start it with `offside up` (or ./demo.sh from the offside repo), then push again.")
    print(f"  Offside: {verdict}")
    print("  (Set OFFSIDE_FAIL_OPEN=0 to block pushes when Offside is down.)")
    print(f"{bar}\n")
    return 0 if config.FAIL_OPEN else 1


if __name__ == "__main__":
    main()
