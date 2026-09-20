import os

import pytest


@pytest.fixture(autouse=True)
def no_real_model_credentials(monkeypatch):
    """Tests must never hit a real model API. Some test modules import app.main,
    which calls load_dotenv() and can leak real OpenAI credentials into the
    process env, silently turning "deterministic" pipeline tests into live
    network calls. Strip them unconditionally so get_provider() always falls
    back to the rule-based provider during tests."""
    for key in ("OPENAI_API_KEY", "OPENAI_FAST_MODEL_ID", "OPENAI_DEEP_MODEL_ID"):
        monkeypatch.delenv(key, raising=False)
