import { useEffect, useState } from "react";
import { VAR_REVIEW_GIF } from "../lib/gifs";

export function VarIntro({ onDone, skip }: { onDone: () => void; skip?: boolean }) {
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    if (skip) {
      onDone();
      return;
    }
    const t1 = setTimeout(() => setPhase(1), 900);
    const t2 = setTimeout(() => onDone(), 2200);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [skip]);

  return (
    <div className="var-intro">
      <div className="pitch-lines" aria-hidden="true">
        <div className="pitch-circle" />
      </div>

      {VAR_REVIEW_GIF ? (
        <img src={VAR_REVIEW_GIF} alt="VAR review" className="var-gif" />
      ) : (
        <div className={`var-box ${phase === 1 ? "var-box-active" : ""}`}>
          <svg className="whistle-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              d="M3 10.5c0-1.1.9-2 2-2h5.5l2-2.5H17a4 4 0 0 1 4 4 4 4 0 0 1-4 4h-1.2a4 4 0 1 1-7.6-2H5c-1.1 0-2-.9-2-2Z"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinejoin="round"
            />
            <circle cx="10" cy="14.5" r="2.6" stroke="currentColor" strokeWidth="1.4" />
          </svg>
          VAR
        </div>
      )}
      <div className="var-caption">CHECKING FOR SLOP...</div>
    </div>
  );
}
