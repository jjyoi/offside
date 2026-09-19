from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models import ReviewSession, ReviewStatus
from app.pipeline.review import run_appeal_investigation, run_review
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


class CreateReviewResponse(BaseModel):
    session_id: str
    review_url: str


class AppealRequest(BaseModel):
    finding_id: str
    text: str


_repo_paths: dict[str, str | None] = {}


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

    from app.models import AppealOutcome, Severity

    overturned_ids = {a.finding_id for a in session.appeals if a.outcome == AppealOutcome.overturned}
    has_red = any(f.severity == Severity.red and f.id not in overturned_ids for f in session.findings)
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
    finding = next((f for f in session.findings if f.id == req.finding_id), None)
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found")

    repo_path = _repo_paths.get(session_id)
    asyncio.create_task(run_appeal_investigation(session_id, req.finding_id, req.text, repo_path))
    return {"status": "appeal_started"}
