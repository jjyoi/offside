from __future__ import annotations

import os

BACKEND_URL = os.environ.get("OFFSIDE_BACKEND_URL", "http://localhost:8000")
FRONTEND_URL = os.environ.get("OFFSIDE_FRONTEND_URL", "http://localhost:3000")

# Hard timeout so `git push` is never stranded waiting on the backend/browser.
WAIT_TIMEOUT_SECONDS = float(os.environ.get("OFFSIDE_WAIT_TIMEOUT", "600"))

# Fail-open policy: if the backend is unreachable, allow the push rather than block development.
FAIL_OPEN = os.environ.get("OFFSIDE_FAIL_OPEN", "1") != "0"
