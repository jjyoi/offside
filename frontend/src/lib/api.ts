import type { ExplanationLevel, FixDecision, ReviewSession } from "./types";

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

export async function continuePush(sessionId: string): Promise<{ status: "approved" | "blocked" }> {
  const resp = await fetch(`${BACKEND_URL}/api/reviews/${sessionId}/continue`, { method: "POST" });
  if (!resp.ok) throw new Error(`Failed to continue push: ${resp.status}`);
  return resp.json();
}

export async function decideFix(sessionId: string, findingId: string, decision: FixDecision): Promise<void> {
  const resp = await fetch(`${BACKEND_URL}/api/reviews/${sessionId}/findings/${findingId}/fix`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
  if (!resp.ok) throw new Error(`Failed to record decision: ${resp.status}`);
}

export async function fetchLevel(): Promise<ExplanationLevel> {
  const resp = await fetch(`${BACKEND_URL}/api/settings`);
  if (!resp.ok) throw new Error(`Failed to load settings: ${resp.status}`);
  return (await resp.json()).level;
}

export async function saveLevel(level: ExplanationLevel): Promise<void> {
  const resp = await fetch(`${BACKEND_URL}/api/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ level }),
  });
  if (!resp.ok) throw new Error(`Failed to save settings: ${resp.status}`);
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
    "fix.decided",
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
