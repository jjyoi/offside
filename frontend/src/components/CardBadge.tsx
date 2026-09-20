import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "motion/react";
import type { Severity } from "../lib/types";
import { WHISTLE_GIF } from "../lib/gifs";
import { playCardStamp } from "../lib/sound";

const LABELS: Record<Severity, string> = {
  play_on: "PLAY ON",
  yellow: "YELLOW CARD!",
  red: "RED CARD — SLOP DETECTED!!!",
};

const SLAP_CAPTIONS: Partial<Record<Severity, string>> = {
  yellow: "YELLOW CARD!",
  red: "RED CARD!!!",
};

const SLAP_DURATION_MS = 2000;

interface Props {
  severity: Severity;
  muted?: boolean;
  suppressGif?: boolean;
  /** Player being booked — printed on the card during the slap. */
  playerName?: string | null;
  /** Bump this to re-trigger the full slap animation (e.g. a failed contest). */
  bookingKey?: number;
  /** Caption shown under the card instead of the default YELLOW/RED CARD text. */
  bookingCaption?: string;
}

export function CardBadge({ severity, muted, suppressGif, playerName, bookingKey = 0, bookingCaption }: Props) {
  const played = useRef(false);
  const lastBookingKey = useRef(bookingKey);
  const [slapping, setSlapping] = useState(!muted && severity !== "play_on");

  useEffect(() => {
    if (played.current || muted) return;
    played.current = true;
    if (severity !== "play_on") {
      playCardStamp();
    }
  }, [severity, muted]);

  useEffect(() => {
    if (severity === "play_on") return;
    const timer = setTimeout(() => setSlapping(false), SLAP_DURATION_MS);
    return () => clearTimeout(timer);
  }, [severity]);

  useEffect(() => {
    if (bookingKey === lastBookingKey.current) return;
    lastBookingKey.current = bookingKey;
    playCardStamp();
    setSlapping(true);
    const timer = setTimeout(() => setSlapping(false), SLAP_DURATION_MS);
    return () => clearTimeout(timer);
  }, [bookingKey]);

  const caption = bookingCaption ?? SLAP_CAPTIONS[severity];

  return (
    <div className={`card-badge card-${severity}`}>
      {createPortal(<AnimatePresence>
        {slapping && (
          <motion.div
            className="card-slap-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <motion.div
              className={`card-slap-rect card-slap-${severity}`}
              initial={{ scale: 3.2, opacity: 0, rotate: -14, y: -60 }}
              animate={{ scale: 1, opacity: 1, rotate: -4, y: 0 }}
              exit={{ scale: 0.35, opacity: 0, rotate: 2, y: 0, transition: { duration: 0.35, ease: "easeIn" } }}
              transition={{ type: "spring", stiffness: 380, damping: 22, mass: 0.9 }}
            >
              {playerName && (
                <motion.span
                  className="card-slap-name"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.4, duration: 0.3 }}
                >
                  {playerName}
                </motion.span>
              )}
            </motion.div>
            {caption && (
              <motion.div
                className={`card-slap-caption card-slap-caption-${severity}`}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8, transition: { duration: 0.25 } }}
                transition={{ delay: 0.35, duration: 0.4, ease: "easeOut" }}
              >
                {caption}
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>, document.body)}

      {severity === "play_on" && !suppressGif && WHISTLE_GIF && <img src={WHISTLE_GIF} alt="" className="card-gif" />}
      {severity !== "play_on" && !slapping && (
        <motion.div
          className={`card-rect card-rect-${severity}`}
          aria-hidden="true"
          initial={{ opacity: 0, scale: 0.6 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: "spring", stiffness: 340, damping: 18 }}
        />
      )}

      <motion.span
        className="card-label"
        initial={{ opacity: 0, x: -6 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: muted ? 0 : severity === "play_on" ? 0.12 : SLAP_DURATION_MS / 1000, duration: 0.25 }}
      >
        {LABELS[severity]}
      </motion.span>
    </div>
  );
}
