import pytest

from app.models import ReviewSession, ReviewStatus
from app.pipeline.review import run_appeal_investigation, run_review
from app.store import SessionStore

RED_DIFF = """diff --git a/checkout/client.ts b/checkout/client.ts
index d7d2320..3e5f4ab 100644
--- a/checkout/client.ts
+++ b/checkout/client.ts
@@ -1,3 +1,3 @@
 export function runQuery(userInput: string) {
-  return safeQuery(userInput);
+  return eval(userInput);
 }
"""

CLEAN_DIFF = """diff --git a/a.ts b/a.ts
index 1111111..2222222 100644
--- a/a.ts
+++ b/a.ts
@@ -1,1 +1,1 @@
-const a = 1;
+const a = 2;
"""


@pytest.fixture(autouse=True)
def patched_store(monkeypatch):
    """Point the pipeline module at a fresh store per test so tests don't share state."""
    fresh = SessionStore()
    monkeypatch.setattr("app.pipeline.review.store", fresh)
    return fresh


async def test_clean_diff_auto_approves(patched_store):
    session = ReviewSession(repo="r", branch="b", local_sha="s", diff=CLEAN_DIFF)
    await patched_store.create(session)

    await run_review(session.id, repo_path=None)

    result = patched_store.get(session.id)
    assert result.status == ReviewStatus.approved
    assert result.findings == []
    assert result.hp_after == 100


async def test_red_finding_awaits_developer_action(patched_store):
    session = ReviewSession(repo="r", branch="b", local_sha="s", diff=RED_DIFF)
    await patched_store.create(session)

    await run_review(session.id, repo_path=None)

    result = patched_store.get(session.id)
    assert result.status == ReviewStatus.awaiting_appeal
    assert len(result.findings) == 1
    assert result.findings[0].severity == "red"
    assert result.hp_after < result.hp_before


async def test_appeal_with_weak_claim_stands_and_stays_blocked(patched_store):
    session = ReviewSession(repo="r", branch="b", local_sha="s", diff=RED_DIFF)
    await patched_store.create(session)
    await run_review(session.id, repo_path=None)

    finding_id = patched_store.get(session.id).findings[0].id
    await run_appeal_investigation(session.id, finding_id, "trust me it's fine", repo_path=None)

    result = patched_store.get(session.id)
    assert result.appeals[-1].outcome == "stands"
    assert result.status == ReviewStatus.awaiting_appeal
    assert len(result.findings) == 1


async def test_appeal_outcome_recorded_with_hypothesis_and_evidence(patched_store):
    session = ReviewSession(repo="r", branch="b", local_sha="s", diff=RED_DIFF)
    await patched_store.create(session)
    await run_review(session.id, repo_path=None)

    finding_id = patched_store.get(session.id).findings[0].id
    await run_appeal_investigation(session.id, finding_id, "input is sanitized upstream", repo_path=None)

    result = patched_store.get(session.id)
    appeal = result.appeals[-1]
    assert appeal.finding_id == finding_id
    assert appeal.claimed_hypothesis == "input is sanitized upstream"
    assert appeal.outcome in ("overturned", "stands")
