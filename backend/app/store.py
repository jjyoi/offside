from __future__ import annotations

import asyncio
import time

from app.models import ReviewEvent, ReviewSession


class SessionStore:
    """In-memory review session store with per-session pub/sub for SSE.

    A single-process store is sufficient for the hackathon MVP: the CLI,
    backend, and browser all talk to one local backend instance.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, ReviewSession] = {}
        self._subscribers: dict[str, list[asyncio.Queue[ReviewEvent]]] = {}
        self._lock = asyncio.Lock()

    async def create(self, session: ReviewSession) -> ReviewSession:
        async with self._lock:
            self._sessions[session.id] = session
            self._subscribers[session.id] = []
        return session

    def get(self, session_id: str) -> ReviewSession | None:
        return self._sessions.get(session_id)

    async def update(self, session_id: str, **fields) -> ReviewSession:
        async with self._lock:
            session = self._sessions[session_id]
            for key, value in fields.items():
                setattr(session, key, value)
            session.updated_at = time.time()
        return session

    async def emit(self, session_id: str, event_type: str, data: dict | None = None) -> ReviewEvent:
        event = ReviewEvent(type=event_type, data=data or {})
        async with self._lock:
            session = self._sessions[session_id]
            session.timeline.append(event)
            session.updated_at = time.time()
            queues = list(self._subscribers.get(session_id, []))
        for queue in queues:
            await queue.put(event)
        return event

    async def subscribe(self, session_id: str) -> asyncio.Queue[ReviewEvent]:
        queue: asyncio.Queue[ReviewEvent] = asyncio.Queue()
        async with self._lock:
            self._subscribers.setdefault(session_id, []).append(queue)
        return queue

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue[ReviewEvent]) -> None:
        async with self._lock:
            subs = self._subscribers.get(session_id, [])
            if queue in subs:
                subs.remove(queue)

    async def wait_for_terminal(self, session_id: str, timeout: float) -> ReviewSession:
        """Poll until status is approved/blocked or timeout elapses."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            session = self._sessions[session_id]
            if session.status in ("approved", "blocked"):
                return session
            await asyncio.sleep(0.25)
        return self._sessions[session_id]


store = SessionStore()
