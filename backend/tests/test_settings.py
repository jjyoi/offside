import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OFFSIDE_CONFIG_DIR", str(tmp_path))
    return TestClient(app)


def test_default_level_is_mid(client):
    assert client.get("/api/settings").json() == {"level": "mid"}


def test_update_persists(client):
    assert client.put("/api/settings", json={"level": "staff"}).status_code == 200
    assert client.get("/api/settings").json() == {"level": "staff"}


def test_rejects_unknown_level(client):
    assert client.put("/api/settings", json={"level": "wizard"}).status_code == 422


def test_keeps_other_keys_in_shared_file(client, tmp_path):
    (tmp_path / "config.json").write_text('{"other": "keep"}')
    client.put("/api/settings", json={"level": "intern"})
    assert '"other": "keep"' in (tmp_path / "config.json").read_text()
