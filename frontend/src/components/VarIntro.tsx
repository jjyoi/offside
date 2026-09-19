import { useEffect, useState } from "react";

export function VarIntro({ onDone, skip }: { onDone: () => void; skip?: boolean }) {
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    if (skip) {
      onDone();
      return;
    }
    const t1 = setTimeout(() => setPhase(1), 900);
    const t2 = setTimeout(() => onDone(), 1900);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [skip]);

  return (
    <div className="var-intro">
      <div className={`var-box ${phase === 1 ? "var-box-active" : ""}`}>VAR</div>
      <div className="var-caption">CHECKING POSSIBLE OFFENCE...</div>
    </div>
  );
}
