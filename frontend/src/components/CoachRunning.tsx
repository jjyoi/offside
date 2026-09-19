import { COACH_RUNNING_GIF } from "../lib/gifs";

export function CoachRunning() {
  if (COACH_RUNNING_GIF) {
    return (
      <div className="coach-running">
        <img src={COACH_RUNNING_GIF} alt="Coach running onto the pitch" className="coach-gif" />
        <div className="coach-caption">Investigating your claim...</div>
      </div>
    );
  }

  return (
    <div className="coach-running">
      <div className="coach-track">
        <svg className="coach-figure" viewBox="0 0 40 60" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="22" cy="8" r="5" fill="currentColor" />
          <path
            d="M22 13 L18 30 M22 13 L28 28 M22 20 L10 26 M22 20 L33 16 M18 30 L10 48 M28 28 L32 50"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
          />
        </svg>
      </div>
      <div className="coach-caption">Coach is running onto the pitch... investigating your claim.</div>
    </div>
  );
}
