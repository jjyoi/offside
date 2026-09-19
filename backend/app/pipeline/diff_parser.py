from __future__ import annotations

import re
from dataclasses import dataclass, field

_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
_FILE_HEADER = re.compile(r"^\+\+\+ b/(.+)$")


@dataclass
class DiffHunk:
    file: str
    added_lines: list[tuple[int, str]] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)
    raw: str = ""


def parse_diff(diff: str) -> list[DiffHunk]:
    """Minimal unified-diff parser: yields per-hunk added/removed lines with line numbers."""
    hunks: list[DiffHunk] = []
    current_file = "unknown"
    current_hunk: DiffHunk | None = None
    line_no = 0
    raw_lines: list[str] = []

    for line in diff.splitlines():
        file_match = _FILE_HEADER.match(line)
        if file_match:
            current_file = file_match.group(1)
            continue

        hunk_match = _HUNK_HEADER.match(line)
        if hunk_match:
            if current_hunk is not None:
                current_hunk.raw = "\n".join(raw_lines)
                hunks.append(current_hunk)
            line_no = int(hunk_match.group(1))
            current_hunk = DiffHunk(file=current_file)
            raw_lines = [line]
            continue

        if current_hunk is None:
            continue

        raw_lines.append(line)
        if line.startswith("+") and not line.startswith("+++"):
            current_hunk.added_lines.append((line_no, line[1:]))
            line_no += 1
        elif line.startswith("-") and not line.startswith("---"):
            current_hunk.removed_lines.append(line[1:])
        elif not line.startswith("\\"):
            line_no += 1

    if current_hunk is not None:
        current_hunk.raw = "\n".join(raw_lines)
        hunks.append(current_hunk)

    return hunks
