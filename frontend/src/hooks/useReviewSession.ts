import { useEffect, useRef, useState } from "react";
import { fetchReview, subscribeToEvents } from "../lib/api";
import type { ReviewSession } from "../lib/types";

export function useReviewSession(sessionId: string) {
  const [session, setSession] = useState<ReviewSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastEvent, setLastEvent] = useState<{ type: string; data: any } | null>(null);
  const refetchTimer = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetchReview(sessionId)
      .then((s) => !cancelled && setSession(s))
      .catch((e) => !cancelled && setError(String(e)));

    const scheduleRefetch = () => {
      if (refetchTimer.current) window.clearTimeout(refetchTimer.current);
      refetchTimer.current = window.setTimeout(() => {
        fetchReview(sessionId)
          .then((s) => !cancelled && setSession(s))
          .catch(() => {});
      }, 150);
    };

    const unsubscribe = subscribeToEvents(sessionId, (type, data) => {
      if (cancelled) return;
      setLastEvent({ type, data });
      scheduleRefetch();
    });

    return () => {
      cancelled = true;
      unsubscribe();
      if (refetchTimer.current) window.clearTimeout(refetchTimer.current);
    };
  }, [sessionId]);

  return { session, error, lastEvent };
}
