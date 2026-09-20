import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";

const DURATION_MS = 2500;
const FADE_SECONDS = 0.25;
const seen = new Set<string>();

function alreadyPlayed(id: string) {
  if (seen.has(id)) return true;
  try { return sessionStorage.getItem(`offside:play-on:${id}`) === "played"; }
  catch { return false; }
}

export function PlayOnCelebration({ id }: { id: string }) {
  const [visible, setVisible] = useState(() => !alreadyPlayed(id));
  const started = useRef(false);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    if (!visible) return;
    if (!started.current) {
      started.current = true;
      seen.add(id);
      try { sessionStorage.setItem(`offside:play-on:${id}`, "played"); } catch { /* Storage is optional. */ }
    }
    const timer = window.setTimeout(() => setVisible(false), DURATION_MS - FADE_SECONDS * 1000);
    return () => window.clearTimeout(timer);
  }, [id, visible]);

  return createPortal(
    <AnimatePresence>
      {visible && (
        <motion.div className="card-slap-overlay play-on-celebration" role="status" aria-label="Play on!"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: FADE_SECONDS }}>
          {!reducedMotion && <div className="celebration-balls" aria-hidden="true">
            {Array.from({ length: 8 }, (_, index) => (
              <motion.div key={index} className="celebration-ball"
                initial={{ left: `${index * 13}%`, top: `${(index % 3) * 30}%`, rotate: 0 }}
                animate={{
                  left: [`${index * 13}%`, `${100 - index * 13}%`, `${index * 13}%`],
                  top: [`${(index % 3) * 30}%`, "100%", "0%", "100%", "20%"],
                  rotate: index % 2 ? -540 : 540,
                }}
                transition={{ left: { duration: DURATION_MS / 1000, ease: "linear" }, top: { duration: 1.5 + index * 0.12, ease: "easeInOut", repeat: Infinity }, rotate: { duration: DURATION_MS / 1000, ease: "linear" } }}>
                <svg viewBox="0 0 64 64" fill="none">
                  <circle cx="32" cy="32" r="30" fill="#fffdf5" stroke="#19221c" strokeWidth="2" />
                  <path d="M32 20 44 29 39 43 25 43 20 29Z M22 4 27 12 19 21 7 19 10 10Z M42 4 54 10 57 19 45 21 37 12Z M3 32 13 32 18 44 12 53 5 45Z M61 32 51 32 46 44 52 53 59 45Z M23 60 26 51 38 51 41 60Z" fill="#19221c" />
                  <path d="m27 12 5 8 5-8M19 21l1 8-7 3m32-11-1 8 7 3M18 44l7-1 1 8m20-7-7-1-1 8" stroke="#19221c" strokeWidth="1.5" />
                </svg>
              </motion.div>
            ))}
          </div>}
          <motion.div className="play-on-signal"
            initial={reducedMotion ? { opacity: 0 } : { opacity: 0, scale: 2.8, rotate: -12, y: -50 }}
            animate={{ opacity: 1, scale: 1, rotate: -4, y: 0 }}
            transition={reducedMotion ? { duration: 0.2 } : { type: "spring", stiffness: 330, damping: 22 }}>
            <span className="play-on-signal-label">PLAY ON!</span>
            <span className="play-on-signal-caption">The ref gives the all-clear</span>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>, document.body,
  );
}
