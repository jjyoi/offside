import type { ReviewSession } from "./types";

export const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export async function fetchReview(sessionId: string): Promise<ReviewSession> {
  const resp = await fetch(`${BACKEND_URL}/api/reviews/${sessionId}`);
  if (!resp.ok) throw new Error(`Failed to fetch review: ${resp.status}`);
  return resp.json();
}

export async function submitAppeal(sessionId: string, findingId: string, text: string): Promise<void> {
  const resp = await fetch(`${BACKEND_URL}/api/reviews/${sessionId}/appeals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ finding_id: findingId, text }),
  });
  if (!resp.ok) throw new Error(`Failed to submit appeal: ${resp.status}`);
}

export async function continuePush(sessionId: string): Promise<{ status: string }> {
  const resp = await fetch(`${BACKEND_URL}/api/reviews/${sessionId}/continue`, { method: "POST" });
  if (!resp.ok) throw new Error(`Failed to continue push: ${resp.status}`);
  return resp.json();
}

export function subscribeToEvents(sessionId: string, onEvent: (type: string, data: any) => void): () => void {
  const source = new EventSource(`${BACKEND_URL}/api/reviews/${sessionId}/events`);

  const eventTypes = [
    "review.started",
    "check.completed",
    "finding.detected",
    "evidence.added",
    "animation.var_started",
    "verdict.ready",
    "appeal.started",
    "appeal.evidence_added",
    "appeal.completed",
    "review.approved",
    "review.blocked",
  ];

  for (const type of eventTypes) {
    source.addEventListener(type, (evt: MessageEvent) => {
      try {
        onEvent(type, JSON.parse(evt.data));
      } catch {
        onEvent(type, {});
      }
    });
  }

  return () => source.close();
}
