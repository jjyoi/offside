import { useEffect } from "react";
import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "motion/react";

interface Props {
  hpBefore: number;
  hpAfter: number;
}

export function HpBar({ hpBefore, hpAfter }: Props) {
  const value = useMotionValue(hpBefore);
  const rounded = useTransform(value, (hp) => Math.round(hp));
  const width = useTransform(value, (hp) => `${Math.max(0, Math.min(100, hp))}%`);
  const reducedMotion = useReducedMotion();
  useEffect(() => {
    const animation = animate(value, hpAfter, { duration: reducedMotion ? 0 : 0.9, ease: "easeOut" });
    return () => animation.stop();
  }, [hpAfter, value, reducedMotion]);
  const pct = Math.max(0, Math.min(100, hpAfter));
  const damaged = hpAfter < hpBefore;
  return (
    <div className="hp-bar-wrap">
      <div className="hp-label">
        <span>HP</span>
        {damaged && <span className="hp-delta">-{hpBefore - hpAfter}</span>}
        <span className="hp-value">
          <motion.span>{rounded}</motion.span> <span className="hp-max">/ 100</span>
        </span>
      </div>
      <div className="hp-track" role="meter" aria-label="HP" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
        <motion.div
          className={`hp-fill ${pct <= 25 ? "hp-critical" : pct <= 60 ? "hp-warning" : ""}`}
          style={{ width }}
        />
        <div className="hp-ticks" aria-hidden="true" />
      </div>
    </div>
  );
}
