"""Completion regressions; also runnable with stdlib unittest."""
import asyncio
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models import Appeal, AppealOutcome, Finding, ReviewSession, ReviewStatus, Severity
from app.routers import reviews
from app.store import SessionStore


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.store = SessionStore()
        self.patch = patch.object(reviews, "store", self.store)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.pending_patch = patch.object(reviews, "_pending_appeals", set())
        self.pending_patch.start()
        self.addCleanup(self.pending_patch.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def session(self, severity=Severity.red, status=ReviewStatus.awaiting_appeal):
        finding = Finding(file="demo.py", start_line=1, end_line=1, category="security",
                          severity=severity, confidence=.9, explanation="demo", roast="demo", hp_delta=-40)
        session = ReviewSession(repo="demo", branch="demo", local_sha="demo", diff="",
                                status=status, findings=[finding], hp_after=60)
        asyncio.run(self.store.create(session))
        return session

    def complete(self, session):
        return self.client.post(f"/api/reviews/{session.id}/continue")

    def test_red_completes_as_blocked_and_emits_terminal_event(self):
        session = self.session()
        self.assertEqual(self.complete(session).json(), {"status": "blocked"})
        self.assertEqual(session.status, ReviewStatus.blocked)
        self.assertEqual(session.timeline[-1].type, "review.blocked")
        self.assertEqual(self.client.get(f"/api/reviews/{session.id}").json()["status"], "blocked")
        self.assertEqual(self.complete(session).json(), {"status": "blocked"})
        self.assertEqual(len(session.timeline), 1)

    def test_yellow_completes_as_approved(self):
        session = self.session(Severity.yellow)
        self.assertEqual(self.complete(session).json(), {"status": "approved"})
        self.assertEqual(session.timeline[-1].type, "review.approved")

    def test_overturned_red_does_not_block_remaining_yellow(self):
        session = self.session()
        session.appeals.append(Appeal(finding_id=session.findings[0].id, text="verified", outcome=AppealOutcome.overturned))
        session.findings.append(session.findings[0].model_copy(update={"id": "yellow", "severity": Severity.yellow}))
        self.assertEqual(self.complete(session).json(), {"status": "approved"})

    def test_cannot_finish_before_review_or_appeal_completes(self):
        session = self.session(status=ReviewStatus.reviewing)
        self.assertEqual(self.complete(session).status_code, 409)
        session.status = ReviewStatus.awaiting_appeal
        reviews._pending_appeals.add((session.id, session.findings[0].id))
        self.assertEqual(self.complete(session).status_code, 409)
        self.assertEqual(session.status, ReviewStatus.awaiting_appeal)

    def test_completed_review_rejects_new_appeals(self):
        session = self.session()
        self.complete(session)
        response = self.client.post(f"/api/reviews/{session.id}/appeals", json={"finding_id": session.findings[0].id, "text": "wait"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(session.status, ReviewStatus.blocked)
