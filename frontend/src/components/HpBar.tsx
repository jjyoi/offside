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
        {damaged && <span className="hp-delta">-{hpBefore - hpAfter}</span>}
        <span className="hp-value">
          {hpAfter} <span className="hp-max">/ 100</span>
        </span>
      </div>
      <div className="hp-track" role="meter" aria-label="HP" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
        <div
          className={`hp-fill ${pct <= 25 ? "hp-critical" : pct <= 60 ? "hp-warning" : ""}`}
          style={{ width: `${pct}%` }}
        />
        <div className="hp-ticks" aria-hidden="true" />
      </div>
    </div>
  );
}
