import type { Appeal, Finding } from "../lib/types";

interface Props {
  findings: Finding[];
  appeals: Appeal[];
  playerName?: string | null;
  revealedIds: Set<string>;
}

export function BookingsTracker({ findings, appeals, playerName, revealedIds }: Props) {
  const booked = findings.filter((finding) => {
    if (finding.severity === "play_on") return false;
    if (!revealedIds.has(finding.id)) return false;
    const overturned = appeals.some((a) => a.finding_id === finding.id && a.outcome === "overturned");
    return !overturned;
  });

  if (booked.length === 0) return null;

  return (
    <div className="bookings-tracker">
      <span className="eyebrow">Booked this match</span>
      <ul className="bookings-list">
        {booked.map((finding) => (
          <li key={finding.id} className={`booking-row booking-${finding.severity}`}>
            <span className={`booking-chip booking-chip-${finding.severity}`} aria-hidden="true" />
            <span className="booking-name">{playerName || "Unknown developer"}</span>
            <span className="booking-file">{finding.file}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
