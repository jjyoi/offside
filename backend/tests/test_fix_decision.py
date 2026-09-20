import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Finding, ReviewSession, ReviewStatus, Severity
from app.store import SessionStore


@pytest.fixture
def client(monkeypatch):
    fresh = SessionStore()
    monkeypatch.setattr("app.routers.reviews.store", fresh)
    return TestClient(app), fresh


def _session(store, severity=Severity.red):
    finding = Finding(
        file="a.py", start_line=1, end_line=1, category="security", severity=severity,
        confidence=0.9, explanation="x", roast="y", suggested_fix="do better", hp_delta=-40,
    )
    session = ReviewSession(repo="r", branch="b", local_sha="s", diff="", findings=[finding],
                            status=ReviewStatus.awaiting_appeal)
    store._sessions[session.id] = session
    store._subscribers[session.id] = []
    return session, finding


def test_accepting_fix_lets_a_red_card_continue(client):
    c, store = client
    session, finding = _session(store)
    r = c.post(f"/api/reviews/{session.id}/findings/{finding.id}/fix", json={"decision": "accepted"})
    assert r.status_code == 200
    assert c.post(f"/api/reviews/{session.id}/continue").json() == {"status": "approved"}


def test_red_without_a_fix_decision_still_blocks(client):
    c, store = client
    session, _ = _session(store)
    assert c.post(f"/api/reviews/{session.id}/continue").json() == {"status": "blocked"}


def test_conceding_without_a_fix_stops_the_push_immediately(client):
    c, store = client
    session, finding = _session(store, Severity.yellow)
    r = c.post(f"/api/reviews/{session.id}/findings/{finding.id}/fix", json={"decision": "declined"})
    assert r.json() == {"status": "blocked"}
    assert store.get(session.id).status == ReviewStatus.blocked


def test_cannot_decide_after_review_finished(client):
    c, store = client
    session, finding = _session(store)
    store._sessions[session.id].status = ReviewStatus.approved
    r = c.post(f"/api/reviews/{session.id}/findings/{finding.id}/fix", json={"decision": "accepted"})
    assert r.status_code == 409
