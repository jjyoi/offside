from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models import ExplanationLevel, FixDecision, ReviewSession, ReviewStatus
from app.pipeline.review import compute_hp, run_appeal_investigation, run_review
from app.store import store

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

FRONTEND_ORIGIN = os.environ.get("OFFSIDE_FRONTEND_ORIGIN", "http://localhost:3000")


class CreateReviewRequest(BaseModel):
    repo: str
    branch: str
    local_sha: str
    remote_sha: str | None = None
    diff: str
    commits: list[str] = []
    repo_path: str | None = None
    author: str | None = None
    level: ExplanationLevel = ExplanationLevel.mid


class CreateReviewResponse(BaseModel):
    session_id: str
    review_url: str


class AppealRequest(BaseModel):
    finding_id: str
    text: str


class FixDecisionRequest(BaseModel):
    decision: FixDecision


_repo_paths: dict[str, str | None] = {}
_pending_appeals: set[tuple[str, str]] = set()


@router.post("", response_model=CreateReviewResponse)
async def create_review(req: CreateReviewRequest) -> CreateReviewResponse:
    session = ReviewSession(
        repo=req.repo,
        branch=req.branch,
        local_sha=req.local_sha,
        remote_sha=req.remote_sha,
        diff=req.diff,
        commits=req.commits,
        author=req.author,
        level=req.level,
    )
    await store.create(session)
    _repo_paths[session.id] = req.repo_path

    asyncio.create_task(run_review(session.id, req.repo_path))

    return CreateReviewResponse(
        session_id=session.id,
        review_url=f"{FRONTEND_ORIGIN}/review/{session.id}",
    )


@router.get("/{session_id}", response_model=ReviewSession)
async def get_review(session_id: str) -> ReviewSession:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="review session not found")
    return session


@router.get("/{session_id}/wait")
async def wait_review(session_id: str, timeout: float = 300.0) -> dict:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="review session not found")
    final = await store.wait_for_terminal(session_id, timeout=timeout)
    return {"status": final.status.value, "hpAfter": final.hp_after}


@router.post("/{session_id}/approve")
async def force_approve(session_id: str) -> dict:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="review session not found")
    await store.update(session_id, status=ReviewStatus.approved)
    await store.emit(session_id, "review.approved", {"hpAfter": session.hp_after, "manual": True})
    return {"status": "approved"}


@router.post("/{session_id}/block")
async def force_block(session_id: str) -> dict:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="review session not found")
    await store.update(session_id, status=ReviewStatus.blocked)
    await store.emit(session_id, "review.blocked", {"hpAfter": session.hp_after, "manual": True})
    return {"status": "blocked"}


@router.post("/{session_id}/continue")
async def continue_push(session_id: str) -> dict:
    """Developer clicks through after seeing the verdict. Reds stay blocked; anything
    else (play_on / yellow-only) is allowed to proceed."""
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="review session not found")

    if session.status in (ReviewStatus.approved, ReviewStatus.blocked):
        return {"status": session.status.value}
    if session.status != ReviewStatus.awaiting_appeal:
        raise HTTPException(status_code=409, detail="review is still running")
    if any(key[0] == session_id for key in _pending_appeals):
        raise HTTPException(status_code=409, detail="an appeal is still running")

    from app.models import AppealOutcome, Severity

    overturned_ids = {a.finding_id for a in session.appeals if a.outcome == AppealOutcome.overturned}
    has_red = any(
        f.severity == Severity.red and f.id not in overturned_ids and f.fix_decision != FixDecision.accepted
        for f in session.findings
    )
    if any(f.fix_decision == FixDecision.declined for f in session.findings):
        has_red = True
    if session.hp_after <= 0:
        # Knocked out: no HP left means no push, whatever the cards say.
        has_red = True
    if has_red:
        await store.update(session_id, status=ReviewStatus.blocked)
        await store.emit(session_id, "review.blocked", {"hpAfter": session.hp_after})
        return {"status": "blocked"}

    await store.update(session_id, status=ReviewStatus.approved)
    await store.emit(session_id, "review.approved", {"hpAfter": session.hp_after})
    return {"status": "approved"}


@router.post("/{session_id}/appeals")
async def submit_appeal(session_id: str, req: AppealRequest) -> dict:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="review session not found")
    if session.status != ReviewStatus.awaiting_appeal:
        raise HTTPException(status_code=409, detail="review is not accepting appeals")
    finding = next((f for f in session.findings if f.id == req.finding_id), None)
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found")

    key = (session_id, req.finding_id)
    if key in _pending_appeals or any(a.finding_id == req.finding_id for a in session.appeals):
        raise HTTPException(status_code=409, detail="appeal already submitted")
    _pending_appeals.add(key)

    async def investigate() -> None:
        try:
            await run_appeal_investigation(session_id, req.finding_id, req.text, _repo_paths.get(session_id))
        finally:
            _pending_appeals.discard(key)

    asyncio.create_task(investigate())
    return {"status": "appeal_started"}


@router.post("/{session_id}/findings/{finding_id}/fix")
async def decide_fix(session_id: str, finding_id: str, req: FixDecisionRequest) -> dict:
    """Developer's answer to a suggested fix. Accepting lets the push continue (a red card
    no longer blocks it). Conceding without agreeing on a fix stops the push."""
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="review session not found")
    finding = next((f for f in session.findings if f.id == finding_id), None)
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found")
    if session.status in (ReviewStatus.approved, ReviewStatus.blocked):
        raise HTTPException(status_code=409, detail="review already finished")

    findings = [
        f.model_copy(update={"fix_decision": req.decision}) if f.id == finding_id else f for f in session.findings
    ]
    hp_after = compute_hp(session.hp_before, findings, session.appeals)
    await store.update(session_id, findings=findings, hp_after=hp_after)
    await store.emit(
        session_id, "fix.decided", {"findingId": finding_id, "decision": req.decision.value, "hpAfter": hp_after}
    )

    if req.decision == FixDecision.declined:
        await store.update(session_id, status=ReviewStatus.blocked)
        await store.emit(session_id, "review.blocked", {"hpAfter": session.hp_after})
        return {"status": "blocked"}
    return {"status": session.status.value}
