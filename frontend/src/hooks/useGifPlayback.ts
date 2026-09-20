import { useCallback, useEffect, useRef, useState } from "react";

// GIF images have no `ended` event. Start a full-cycle timer after load,
// and keep changing parent callbacks from restarting that timer.
export function useGifPlayback(src: string | null, durationMs: number, onDone: () => void, skip = false) {
  const [ready, setReady] = useState(!src);
  const doneRef = useRef(onDone);
  useEffect(() => { doneRef.current = onDone; }, [onDone]);

  useEffect(() => {
    if (!ready && !skip) return;
    const timer = window.setTimeout(() => doneRef.current(), skip ? 0 : durationMs);
    return () => window.clearTimeout(timer);
  }, [ready, durationMs, skip]);

  const markReady = useCallback(() => setReady(true), []);
  return { onLoad: markReady, onError: markReady };
}
