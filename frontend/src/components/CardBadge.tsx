import type { Severity } from "../lib/types";

const LABELS: Record<Severity, string> = {
  play_on: "PLAY ON",
  yellow: "YELLOW CARD",
  red: "RED CARD",
};

export function CardBadge({ severity }: { severity: Severity }) {
  return (
    <div className={`card-badge card-${severity}`}>
      {severity !== "play_on" && <div className="card-rect" />}
      <span>{LABELS[severity]}</span>
    </div>
  );
}
