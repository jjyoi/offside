import { motion } from "motion/react";
import { CONTEST_INTRO_GIF } from "../lib/gifs";

export function ContestIntro({ onDone }: { onDone: () => void }) {
  return (
    <motion.div
      className="contest-intro-overlay"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      onAnimationComplete={() => {
        const timer = setTimeout(onDone, 1600);
        return () => clearTimeout(timer);
      }}
    >
      {CONTEST_INTRO_GIF ? (
        <motion.img
          src={CONTEST_INTRO_GIF}
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
    </motion.div>
  );
}
