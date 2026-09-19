import { useEffect, useState } from "react";
import type { Severity } from "../lib/types";
import { RED_CARD_GIF, WHISTLE_GIF, YELLOW_CARD_GIF } from "../lib/gifs";

const LABELS: Record<Severity, string> = {
  play_on: "PLAY ON",
  yellow: "YELLOW CARD",
  red: "RED CARD — SLOP DETECTED",
};

const GIFS: Record<Severity, string | null> = {
  play_on: WHISTLE_GIF,
  yellow: YELLOW_CARD_GIF,
  red: RED_CARD_GIF,
};

export function CardBadge({ severity }: { severity: Severity }) {
  const [raised, setRaised] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setRaised(true), 50);
    return () => clearTimeout(t);
  }, []);

  const gif = GIFS[severity];

  return (
    <div className={`card-badge card-${severity}`}>
      {gif ? (
        <img src={gif} alt={LABELS[severity]} className="card-gif" />
      ) : (
        severity !== "play_on" && <div className={`card-rect ${raised ? "card-rect-raised" : ""}`} />
      )}
      <span>{LABELS[severity]}</span>
    </div>
  );
}
