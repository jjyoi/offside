import { motion } from "motion/react";
import type { Appeal, Finding } from "../lib/types";

interface Props {
  findings: Finding[];
  appeals: Appeal[];
  playerName: string;
  revealedIds: Set<string>;
  activeId?: string;
  onSelect: (index: number) => void;
}

export function BookingsTracker({ findings, appeals, playerName, revealedIds, activeId, onSelect }: Props) {
  const booked = findings
    .map((finding, index) => ({ finding, index }))
    .filter(({ finding }) => {
      if (finding.severity === "play_on") return false;
      if (!revealedIds.has(finding.id)) return false;
      const overturned = appeals.some((a) => a.finding_id === finding.id && a.outcome === "overturned");
      return !overturned;
    });

  if (booked.length === 0) return null;

  return (
    <div className="bookings-tracker">
      <span className="eyebrow">Booked this match</span>
      <div className="card-hand">
        {booked.map(({ finding, index }, handIndex) => (
          <motion.button
            key={finding.id}
            type="button"
            className={`hand-card hand-card-${finding.severity} ${finding.id === activeId ? "hand-card-active" : ""}`}
            style={{ zIndex: handIndex, marginLeft: handIndex === 0 ? undefined : -80 }}
            onClick={() => onSelect(index)}
            initial={{ opacity: 0, y: 20, rotate: 0 }}
            animate={{
              opacity: 1,
              y: 0,
              rotate: (handIndex - (booked.length - 1) / 2) * 6,
            }}
            whileHover={{ y: -48, rotate: 0, zIndex: 50, transition: { duration: 0.2 } }}
            transition={{ type: "spring", stiffness: 300, damping: 22 }}
          >
            <span className="hand-card-name">{playerName}</span>
            <span className="hand-card-file">{finding.file}</span>
            <span className="hand-card-category">{finding.category}</span>
          </motion.button>
        ))}
      </div>
    </div>
  );
}
