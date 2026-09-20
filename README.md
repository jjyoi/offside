# Offside

HTN2026

A Git pre-push referee. `git push` pauses, Offside inspects the outgoing diff, gathers evidence, and opens a browser-based VAR review. Suspicious code gets a technical finding, a roast, and a card with an HP deduction. You can contest the call; Offside investigates deeper and either overturns the decision or lets it stand. See [OFFSIDE_SPEC.md](OFFSIDE_SPEC.md) for the full design.

## Project layout

```
backend/   FastAPI review server — source of truth for session state
frontend/  Vite + React VAR review UI
cli/       Python CLI + git pre-push hook installer
```

## Setup

Requires Python 3.11+, Node 18+, and `uv` (or `pip`).

```sh
# Backend
cd backend
uv venv .venv && uv pip install -e . --python .venv/bin/python

# Frontend
cd ../frontend
npm install

# CLI
cd ../cli
uv venv .venv && uv pip install -e . --python .venv/bin/python
```

## Running the demo

Start the backend and frontend (each in their own terminal):

```sh
# Terminal 1
cd backend && .venv/bin/uvicorn app.main:app --port 8000

# Terminal 2
cd frontend && npm run dev   # serves on http://localhost:3000
```

Install the hook into any local git repo you want to protect, and make sure `offside` is on your `PATH`:

```sh
export PATH="/path/to/offside/cli/.venv/bin:$PATH"
cd /path/to/some/repo
offside install
```

Now `git push` from that repo will pause, open a browser VAR review, and allow or block the push based on the verdict.

## Model provider

Review verdicts come from `backend/app/pipeline/provider.py`. If `OPENAI_API_KEY` is set, Offside calls the OpenAI API for the fast and deep review passes. Without it, it falls back to a deterministic rule-based referee so the full pipeline (evidence gathering, cards, appeals) works end-to-end with no external dependency.

```sh
export OPENAI_API_KEY=...
export OPENAI_FAST_MODEL_ID=gpt-4o-mini   # cheap/fast pass (default if unset)
export OPENAI_DEEP_MODEL_ID=gpt-4o        # deeper investigation/appeal pass (default if unset)
```

`OPENAI_FAST_MODEL_ID` / `OPENAI_DEEP_MODEL_ID` are optional — they default to `gpt-4o-mini` and `gpt-4o` respectively. Use a smaller/faster model for the fast tier and a stronger one for the deep tier per the spec's fast/deep routing.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `OFFSIDE_BACKEND_URL` | `http://localhost:8000` | CLI → backend |
| `OFFSIDE_FRONTEND_URL` | `http://localhost:3000` | Used to build the review URL printed/opened by the CLI |
| `OFFSIDE_FRONTEND_ORIGIN` | `http://localhost:3000` | Backend CORS allow-origin |
| `OFFSIDE_WAIT_TIMEOUT` | `600` | Seconds the CLI waits for a verdict before failing open |
| `OFFSIDE_FAIL_OPEN` | `1` | If the backend is unreachable or times out, `1` allows the push, `0` blocks it |

## Tests

```sh
cd backend && .venv/bin/python -m pytest tests/ -v
cd cli && .venv/bin/python -m pytest tests/ -v
```

## Bypass

Local hooks can be skipped with `git push --no-verify`. That's expected for the hackathon; a real deployment would add a required GitHub status check instead.
