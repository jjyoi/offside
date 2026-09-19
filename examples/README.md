# Several-findings demo

`flagged_demo.py` contains four intentionally flawed examples:

- User input evaluated as Python code: security, red card.
- A hardcoded staff password (a fake demo value): security, yellow card.
- A broad exception handler that silently returns a zero score: reliability, yellow card.
- An unfinished refund that reports success without refunding: maintainability, yellow card.

These are the expected results with Offside's rule-based fallback. A configured
model may assign different categories or severities.

Start the backend and frontend as described in the root README, then run from
the repository root:

```sh
python3 examples/review_demo.py
```

Open the printed URL to see the findings and try the review/contest flow.
The launcher only reads the fixture and submits its diff; it never executes
the flawed functions, modifies git, or pushes anything. It compares the functions
against placeholder implementations with one line of diff context, producing
four separate hunks because Offside currently returns one finding per hunk.
Simply adding the entire fixture in a commit would normally produce one hunk
and therefore only one finding.

Set `OFFSIDE_BACKEND_URL` if the backend is running somewhere other than
`http://localhost:8000`.
