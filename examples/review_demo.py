"""Submit the intentionally flawed fixture as separate review hunks."""

import ast
import difflib
import json
import os
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


def build_demo_diff():
    fixture = Path(__file__).with_name("flagged_demo.py")
    source = fixture.read_text()
    after = source.splitlines(keepends=True)
    before = after.copy()
    # Compare against unimplemented functions so each body gets its own hunk.
    # Parse the fixture as text; never import or execute its unsafe examples.
    functions = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)]
    for function in reversed(functions):
        before[function.lineno:function.end_lineno] = ["    raise NotImplementedError\n"]
    return "".join(difflib.unified_diff(
        before, after,
        fromfile="a/examples/flagged_demo.py",
        tofile="b/examples/flagged_demo.py",
        n=1,
    ))


def main():
    backend = os.environ.get("OFFSIDE_BACKEND_URL", "http://localhost:8000").rstrip("/")
    payload = {
        "repo": "offside-demo",
        "repo_path": str(Path(__file__).resolve().parents[1]),
        "branch": "demo/several-findings",
        "local_sha": "demo-working-copy",
        "diff": build_demo_diff(),
    }
    request = Request(
        f"{backend}/api/reviews",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            result = json.load(response)
    except URLError as error:
        raise SystemExit(f"Could not create demo review at {backend}: {error}") from error
    print(f"Open the demo review: {result['review_url']}")


if __name__ == "__main__":
    main()
