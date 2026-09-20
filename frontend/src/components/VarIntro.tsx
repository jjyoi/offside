import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { VAR_REVIEW_GIF, VAR_REVIEW_DURATION_MS } from "../lib/gifs";
import { useGifPlayback } from "../hooks/useGifPlayback";

export function VarIntro({ onDone, skip }: { onDone: () => void; skip?: boolean }) {
  const [phase, setPhase] = useState(0);
  const playback = useGifPlayback(VAR_REVIEW_GIF, Math.max(1900, VAR_REVIEW_DURATION_MS + 300), onDone, skip);

  useEffect(() => {
    const t1 = setTimeout(() => setPhase(1), 700);
    return () => {
      clearTimeout(t1);
    };
  }, [skip]);

  return (
    <motion.div
      className="var-intro"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      <div className="monitor">
        <div className="monitor-bar">
          <span className="rec">
            <i aria-hidden="true" />
            Live
          </span>
          <span>VAR Room</span>
        </div>
        <div className="monitor-screen">
          {VAR_REVIEW_GIF ? (
            <img src={VAR_REVIEW_GIF} {...playback} alt="VAR review in progress" className="var-gif" />
          ) : (
            <motion.div
              className="var-box"
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: phase === 1 ? 1.04 : 1, opacity: 1 }}
              transition={{ type: "spring", stiffness: 260, damping: 20 }}
            >
              <svg className="whistle-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path
                  d="M3 10.5c0-1.1.9-2 2-2h5.5l2-2.5H17a4 4 0 0 1 4 4 4 4 0 0 1-4 4h-1.2a4 4 0 1 1-7.6-2H5c-1.1 0-2-.9-2-2Z"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinejoin="round"
                />
                <circle cx="10" cy="14.5" r="2.6" stroke="currentColor" strokeWidth="1.6" />
              </svg>
              VAR
            </motion.div>
          )}
        </div>
      </div>

      <div className="var-caption">Checking for slop</div>
    </motion.div>
  );
}
