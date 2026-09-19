from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.store import store

router = APIRouter(prefix="/api/reviews", tags=["events"])


@router.get("/{session_id}/events")
async def review_events(session_id: str, request: Request) -> EventSourceResponse:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="review session not found")

    queue = await store.subscribe(session_id)

    async def event_generator():
        try:
            for evt in session.timeline:
                yield {"event": evt.type, "data": json.dumps({"id": evt.id, **evt.data})}

            while True:
                if await request.is_disconnected():
                    break
                try:
                    evt = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield {"event": evt.type, "data": json.dumps({"id": evt.id, **evt.data})}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            await store.unsubscribe(session_id, queue)

    return EventSourceResponse(event_generator())
