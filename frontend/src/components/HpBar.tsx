interface Props {
  hpBefore: number;
  hpAfter: number;
}

export function HpBar({ hpBefore, hpAfter }: Props) {
  const pct = Math.max(0, Math.min(100, hpAfter));
  const damaged = hpAfter < hpBefore;
  return (
    <div className="hp-bar-wrap">
      <div className="hp-label">
        <span>HP</span>
        <span>
          {hpAfter} / 100 {damaged && <span className="hp-delta">(-{hpBefore - hpAfter})</span>}
        </span>
      </div>
      <div className="hp-track">
        <div
          className={`hp-fill ${pct <= 25 ? "hp-critical" : pct <= 60 ? "hp-warning" : ""}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
