import { createPortal } from "react-dom";
import { motion } from "motion/react";
import { CONTEST_INTRO_GIF, CONTEST_INTRO_DURATION_MS } from "../lib/gifs";
import { useGifPlayback } from "../hooks/useGifPlayback";

export function ContestIntro({ onDone }: { onDone: () => void }) {
  const playback = useGifPlayback(CONTEST_INTRO_GIF, CONTEST_INTRO_GIF ? CONTEST_INTRO_DURATION_MS + 400 : 1800, onDone);
  return createPortal(
    <motion.div
      className="contest-intro-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
    >
      {CONTEST_INTRO_GIF ? (
        <motion.img
          src={CONTEST_INTRO_GIF}
          {...playback}
          alt="Coach storming onto the pitch to contest the call"
          className="contest-intro-gif"
          initial={{ scale: 0.7, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 260, damping: 22 }}
        />
      ) : (
        <motion.div
          className="contest-intro-fallback"
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 260, damping: 22 }}
        >
          Coach is storming the pitch
        </motion.div>
      )}
      <motion.div
        className="contest-intro-caption"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: 0.35 }}
      >
        Make your case
      </motion.div>
    </motion.div>,
    document.body,
  );
}
