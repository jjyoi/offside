import pytest

from app.models import Finding, ReviewSession, ReviewStatus, Severity
from app.pipeline import review as review_module
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
    # A failed challenge on a confident red card takes the last of the HP, which blocks the push.
    assert result.status == ReviewStatus.blocked
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


class _AlwaysOverturnProvider:
    """Stub provider that always rules in the developer's favor, so we can test
    the overturned-finding bookkeeping without depending on LLM judgment."""

    name = "stub-overturn"

    async def complete(self, system, prompt):
        from app.pipeline.provider import ModelResult, RefereeVerdict

        verdict = RefereeVerdict(offence=False, severity="play_on", confidence=0.9, explanation="cleared", roast="")
        return ModelResult(verdict=verdict, latency_ms=0.0, model_name=self.name, raw="{}")


async def test_overturned_finding_stays_visible_and_stops_blocking(patched_store, monkeypatch):
    """Regression test: an overturned finding must remain in session.findings
    (so the browser can render the 'DECISION OVERTURNED' card) while no longer
    contributing to HP loss or blocking the push."""
    session = ReviewSession(repo="r", branch="b", local_sha="s", diff=RED_DIFF)
    await patched_store.create(session)
    await run_review(session.id, repo_path=None)

    finding_id = patched_store.get(session.id).findings[0].id

    monkeypatch.setattr(review_module, "get_provider", lambda tier: _AlwaysOverturnProvider())
    await run_appeal_investigation(session.id, finding_id, "the caller already handles this", repo_path=None)

    result = patched_store.get(session.id)
    assert result.appeals[-1].outcome == "overturned"
    assert len(result.findings) == 1  # finding is NOT removed
    assert result.findings[0].id == finding_id
    assert result.hp_after == result.hp_before  # HP fully restored
    assert result.status == ReviewStatus.approved  # no longer blocks


class _AlwaysDowngradeProvider:
    """Stub provider that always talks a red card down to yellow (a partial win: the
    ref keeps a real concern but drops the blocking severity), so we can test the
    downgrade bookkeeping without depending on LLM judgment."""

    name = "stub-downgrade"

    async def complete(self, system, prompt):
        from app.pipeline.provider import ModelResult, RefereeVerdict

        verdict = RefereeVerdict(
            offence=True, severity="yellow", confidence=0.6, explanation="partially justified", roast=""
        )
        return ModelResult(verdict=verdict, latency_ms=0.0, model_name=self.name, raw="{}")


async def test_downgraded_red_becomes_yellow_with_no_penalty_and_stops_blocking(patched_store, monkeypatch):
    """A red card talked down to yellow: the finding's own severity/hp_delta change to the
    yellow-equivalent cost, no appeal penalty applies (it's a partial win, not a lost bet),
    and the push is no longer blocked once no red findings remain."""
    session = ReviewSession(repo="r", branch="b", local_sha="s", diff=RED_DIFF)
    await patched_store.create(session)
    await run_review(session.id, repo_path=None)

    before = patched_store.get(session.id)
    finding = before.findings[0]
    assert finding.severity == Severity.red
    hp_with_red_card = before.hp_after

    monkeypatch.setattr(review_module, "get_provider", lambda tier: _AlwaysDowngradeProvider())
    await run_appeal_investigation(session.id, finding.id, "the caller partially handles this", repo_path=None)

    result = patched_store.get(session.id)
    appeal = result.appeals[-1]
    assert appeal.outcome == "downgraded"
    assert appeal.downgraded_severity == "yellow"
    assert appeal.hp_penalty == 0  # no penalty for a partial win

    downgraded = next(f for f in result.findings if f.id == finding.id)
    assert downgraded.severity == Severity.yellow
    assert downgraded.hp_delta != finding.hp_delta  # recomputed at yellow's (smaller) cost
    assert downgraded.hp_delta > finding.hp_delta  # smaller HP loss than the original red

    # HP recovers some ground versus staying red, but isn't fully restored like an overturn.
    assert result.hp_after > hp_with_red_card
    assert result.hp_after < result.hp_before

    assert result.status == ReviewStatus.approved  # no red findings left, so nothing blocks


@pytest.mark.parametrize("level,check", [
    ("staff", lambda t: len(t) < 60),
    ("mid", lambda t: "Detected potential" in t),
    ("intern", lambda t: "Detected potential" in t and len(t) > 200),
])
async def test_explanation_depth_follows_level(patched_store, level, check):
    session = ReviewSession(repo="r", branch="b", local_sha="s", diff=RED_DIFF, level=level)
    await patched_store.create(session)
    await run_review(session.id, repo_path=None)
    assert check(patched_store.get(session.id).findings[0].explanation)


def test_level_defaults_to_mid_and_rejects_unknown():
    assert ReviewSession(repo="r", branch="b", local_sha="s", diff="").level.value == "mid"
    with pytest.raises(ValueError):
        ReviewSession(repo="r", branch="b", local_sha="s", diff="", level="wizard")


async def test_rule_based_findings_carry_a_suggested_fix(patched_store):
    session = ReviewSession(repo="r", branch="b", local_sha="s", diff=RED_DIFF)
    await patched_store.create(session)
    await run_review(session.id, repo_path=None)
    assert patched_store.get(session.id).findings[0].suggested_fix


LIGHT_DIFF = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,1 +1,3 @@
 x = 1
+# TODO tidy this up
+print("debug")
"""

GUARD_DIFF = """diff --git a/api.ts b/api.ts
--- a/api.ts
+++ b/api.ts
@@ -1,2 +1,2 @@
-const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
+const res = await fetch(url);
"""

SECRET_DIFF = """diff --git a/auth.py b/auth.py
--- a/auth.py
+++ b/auth.py
@@ -1,1 +1,2 @@
 import os
+password = "hunter2"
"""


async def _severities(patched_store, diff, level):
    session = ReviewSession(repo="r", branch="b", local_sha="s", diff=diff, level=level)
    await patched_store.create(session)
    await run_review(session.id, repo_path=None)
    return [f.severity.value for f in patched_store.get(session.id).findings]


async def test_light_issues_get_a_pass_for_everyone_but_mid(patched_store):
    assert await _severities(patched_store, LIGHT_DIFF, "intern") == []
    assert await _severities(patched_store, LIGHT_DIFF, "staff") == []
    assert await _severities(patched_store, LIGHT_DIFF, "mid") == ["yellow"]


async def test_removed_guard_costs_more_hp_with_seniority(patched_store):
    async def hp_lost(level):
        session = ReviewSession(repo="r", branch="b", local_sha="s", diff=GUARD_DIFF, level=level)
        await patched_store.create(session)
        await run_review(session.id, repo_path=None)
        result = patched_store.get(session.id)
        assert [f.severity.value for f in result.findings] == ["yellow"]
        return result.hp_before - result.hp_after

    assert await hp_lost("intern") < await hp_lost("mid") < await hp_lost("staff")


async def test_swallowed_errors_are_red_only_for_staff(patched_store):
    diff = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,1 +1,4 @@\n x = 1\n+try:\n+    y()\n+except:\n"
    assert await _severities(patched_store, diff, "intern") == ["yellow"]
    assert await _severities(patched_store, diff, "mid") == ["yellow"]
    assert await _severities(patched_store, diff, "staff") == ["red"]


async def test_hardcoded_secret_is_red_only_for_staff(patched_store):
    assert await _severities(patched_store, SECRET_DIFF, "intern") == ["yellow"]
    assert await _severities(patched_store, SECRET_DIFF, "mid") == ["yellow"]
    assert await _severities(patched_store, SECRET_DIFF, "staff") == ["red"]


async def test_egregious_problems_are_red_at_every_level(patched_store):
    diff = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,1 +1,2 @@\n x = 1\n+eval(input())\n"
    for level in ("intern", "mid", "staff"):
        assert await _severities(patched_store, diff, level) == ["red"]


def test_prompt_standard_differs_by_level():
    from app.models import ExplanationLevel
    from app.pipeline.review import level_instruction

    intern = level_instruction(ExplanationLevel.intern)
    staff = level_instruction(ExplanationLevel.staff)
    assert "gently" in intern and "design" not in intern.split("EXPLANATION DEPTH")[0].lower()
    assert "design" in staff.lower() and "high bar" in staff


def test_penalty_grows_with_confidence():
    from app.pipeline.review import appeal_penalty_for

    assert appeal_penalty_for(-56, 0.9) > appeal_penalty_for(-56, 0.5) > appeal_penalty_for(-56, 0.2)
    assert appeal_penalty_for(-56, 0.9) > 56  # losing a confident challenge costs more than the card itself
    assert appeal_penalty_for(0, 0.9) == 0


async def test_failed_contest_costs_hp_and_is_recorded(patched_store):
    session = ReviewSession(repo="r", branch="b", local_sha="s", diff=RED_DIFF)
    await patched_store.create(session)
    await run_review(session.id, repo_path=None)
    before = patched_store.get(session.id)
    finding = before.findings[0]
    hp_with_card = before.hp_after

    await run_appeal_investigation(session.id, finding.id, "trust me it's fine", repo_path=None)

    after = patched_store.get(session.id)
    assert after.appeals[-1].outcome == "stands"
    assert after.appeals[-1].hp_penalty == -finding.appeal_penalty < 0
    assert after.hp_after == hp_with_card - finding.appeal_penalty


async def test_won_contest_restores_the_card_and_charges_nothing(patched_store, monkeypatch):
    session = ReviewSession(repo="r", branch="b", local_sha="s", diff=RED_DIFF)
    await patched_store.create(session)
    await run_review(session.id, repo_path=None)
    finding = patched_store.get(session.id).findings[0]

    class Overturn:
        async def complete(self, system, prompt):
            from app.pipeline.provider import ModelResult, RefereeVerdict

            return ModelResult(RefereeVerdict(offence=False, severity="play_on"), 1.0, "fake", "")

    monkeypatch.setattr(review_module, "get_provider", lambda tier: Overturn())
    await run_appeal_investigation(session.id, finding.id, "the caller sets it", repo_path=None)

    after = patched_store.get(session.id)
    assert after.appeals[-1].outcome == "overturned"
    assert after.appeals[-1].hp_penalty == 0
    assert after.hp_after == after.hp_before


async def test_failed_contest_that_hits_zero_hp_blocks_immediately(patched_store):
    session = ReviewSession(repo="r", branch="b", local_sha="s", diff=RED_DIFF)
    await patched_store.create(session)
    await run_review(session.id, repo_path=None)
    finding = patched_store.get(session.id).findings[0]

    await run_appeal_investigation(session.id, finding.id, "trust me it's fine", repo_path=None)

    result = patched_store.get(session.id)
    assert result.hp_after <= 0
    assert result.status == ReviewStatus.blocked


def test_fix_refund_is_half_the_card():
    from app.pipeline.review import fix_refund_for

    assert fix_refund_for(-56) == 28
    assert fix_refund_for(0) == 0


def _outcomes(hp_delta, confidence, others=()):
    """HP after each way of handling one card, with optional other cards left alone."""
    from app.models import Appeal, AppealOutcome, FixDecision
    from app.pipeline.review import appeal_penalty_for, compute_hp

    def card(decision=None):
        return Finding(
            id="f", file="a.py", start_line=1, end_line=1, category="c", severity=Severity.yellow,
            confidence=confidence, explanation="", roast="", hp_delta=hp_delta, fix_decision=decision,
        )

    rest = [
        Finding(id=f"o{i}", file="b.py", start_line=1, end_line=1, category="c", severity=Severity.yellow,
                confidence=0.5, explanation="", roast="", hp_delta=d)
        for i, d in enumerate(others)
    ]
    lost = Appeal(finding_id="f", text="x", outcome=AppealOutcome.stands,
                  hp_penalty=-appeal_penalty_for(hp_delta, confidence))
    won = Appeal(finding_id="f", text="x", outcome=AppealOutcome.overturned)
    return {
        "ignore": compute_hp(100, [card(), *rest], []),
        "accept": compute_hp(100, [card(FixDecision.accepted), *rest], []),
        "win": compute_hp(100, [card(), *rest], [won]),
        "lose": compute_hp(100, [card(), *rest], [lost]),
        "lose_then_accept": compute_hp(100, [card(FixDecision.accepted), *rest], [lost]),
    }


def test_contest_outcomes_are_always_ordered_around_accepting():
    """Winning gets back at least as much as accepting; losing leaves you with less than accepting."""
    confidences = [0.0, 0.1, 0.35, 0.5, 0.75, 0.9, 1.0]
    for hp_delta in range(-60, -4):
        for confidence in confidences:
            for others in ((), (-57, -54, -30), (-90, -90)):  # includes piles of cards that sink HP below zero
                o = _outcomes(hp_delta, confidence, others)
                ctx = (hp_delta, confidence, others, o)
                assert o["win"] >= o["accept"], ctx
                assert o["lose"] < o["accept"], ctx
                assert o["lose_then_accept"] < o["accept"], ctx
                assert o["accept"] > o["ignore"], ctx


def test_losing_a_contest_always_costs_something():
    from app.pipeline.review import appeal_penalty_for

    assert appeal_penalty_for(-5, 0.0) >= 1
    assert appeal_penalty_for(0, 0.9) == 0
