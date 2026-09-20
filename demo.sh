#!/usr/bin/env bash
# One command to get Offside ready to demo: starts the backend and the review page, waits until both
# are healthy, and tells you how to try it. Ctrl-C stops whatever this script started.
#
#   ./demo.sh                 start (or reuse) the backend and frontend
#   ./demo.sh /path/to/repo   ...then run `offside doctor` in that repo
#
# Ports can be overridden: BACKEND_PORT=8811 FRONTEND_PORT=3811 ./demo.sh

set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_URL="http://localhost:${BACKEND_PORT}"
FRONTEND_URL="http://localhost:${FRONTEND_PORT}"
LOG_DIR="${TMPDIR:-/tmp}/offside-demo"
CLI_PY="$ROOT/cli/.venv/bin/python"
STARTED_PIDS=()

say()  { printf '%s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

healthy() { curl -fsS -m 2 -o /dev/null "$1" 2>/dev/null; }
port_in_use() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

cleanup() {
  if [ "${#STARTED_PIDS[@]}" -gt 0 ]; then
    say ""
    say "Stopping Offside..."
    for pid in "${STARTED_PIDS[@]}"; do kill "$pid" 2>/dev/null; done
    wait 2>/dev/null
  fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# --- prerequisites -----------------------------------------------------------------------------
[ -x "$ROOT/backend/.venv/bin/python" ] || fail "Backend is not set up. Run:  cd backend && uv venv .venv && uv pip install -e . --python .venv/bin/python"
[ -x "$CLI_PY" ]                        || fail "CLI is not set up. Run:  cd cli && uv venv .venv && uv pip install -e . --python .venv/bin/python"
[ -d "$ROOT/frontend/node_modules" ]    || fail "Frontend is not set up. Run:  cd frontend && npm install"
command -v npm  >/dev/null || fail "npm is not installed."
command -v curl >/dev/null || fail "curl is not installed."
mkdir -p "$LOG_DIR"

# --- start (or reuse) a service ----------------------------------------------------------------
# start_service <name> <port> <health-url> <log> <command...>
start_service() {
  local name="$1" port="$2" url="$3" log="$4"; shift 4
  if healthy "$url"; then
    say "  reuse  $name is already running at $url"
    return 0
  fi
  if port_in_use "$port"; then
    fail "Port $port is taken by something that is not a healthy Offside $name. Free it (lsof -nP -iTCP:$port) or pick another port with BACKEND_PORT / FRONTEND_PORT."
  fi
  say "  start  $name on port $port (log: $log)"
  "$@" >"$log" 2>&1 &
  STARTED_PIDS+=("$!")
}

say "Starting Offside..."
export OFFSIDE_FRONTEND_ORIGIN="$FRONTEND_URL"
export VITE_BACKEND_URL="$BACKEND_URL"

start_service backend "$BACKEND_PORT" "$BACKEND_URL/health" "$LOG_DIR/backend.log" \
  bash -c "cd '$ROOT/backend' && exec .venv/bin/python -m uvicorn app.main:app --port $BACKEND_PORT"
start_service frontend "$FRONTEND_PORT" "$FRONTEND_URL" "$LOG_DIR/frontend.log" \
  bash -c "cd '$ROOT/frontend' && exec npm run dev -- --port $FRONTEND_PORT --strictPort"

# --- wait until both answer --------------------------------------------------------------------
wait_healthy() {
  local name="$1" url="$2" log="$3"
  for _ in $(seq 1 60); do
    healthy "$url" && return 0
    sleep 0.5
  done
  printf '\n--- last lines of %s ---\n' "$log" >&2
  tail -n 15 "$log" >&2
  fail "The $name did not become healthy at $url within 30 seconds."
}
wait_healthy backend  "$BACKEND_URL/health" "$LOG_DIR/backend.log"
wait_healthy frontend "$FRONTEND_URL"       "$LOG_DIR/frontend.log"

# --- tell the user what to do ------------------------------------------------------------------
say ""
say "Offside is ready."
say "  backend   $BACKEND_URL"
say "  frontend  $FRONTEND_URL"
if [ "$BACKEND_PORT" != 8000 ] || [ "$FRONTEND_PORT" != 3000 ]; then
  say ""
  say "  Non-default ports: run pushes with"
  say "    OFFSIDE_BACKEND_URL=$BACKEND_URL OFFSIDE_FRONTEND_URL=$FRONTEND_URL git push"
fi
say ""
say "Try it from any repo you want to protect:"
say "  export PATH=\"$ROOT/cli/.venv/bin:\$PATH\"    # only needed to run the offside command yourself"
say "  cd /path/to/repo && offside install        # once per clone; the hook itself needs no PATH"
say "  git push                                   # opens the review in your browser"

if [ "${1:-}" != "" ]; then
  say ""
  (cd "$1" && "$CLI_PY" -m offside doctor) || true
fi

if [ "${#STARTED_PIDS[@]}" -eq 0 ]; then
  say ""
  say "Everything was already running, nothing for this script to manage."
  exit 0
fi
say ""
say "Press Ctrl-C to stop Offside."
# Stay in the foreground; if either service dies, say so instead of silently leaving a dead demo.
while true; do
  for pid in "${STARTED_PIDS[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then
      fail "A service exited unexpectedly. Logs are in $LOG_DIR"
    fi
  done
  sleep 2
done
