import { APPEAL_WAITING_GIF, APPEAL_WAITING_DURATION_MS } from "../lib/gifs";
import { useGifPlayback } from "../hooks/useGifPlayback";

export function AppealWaiting({ onDone }: { onDone: () => void }) {
  const playback = useGifPlayback(APPEAL_WAITING_GIF, APPEAL_WAITING_DURATION_MS + 100, onDone);
  return (
    <div className="appeal-waiting" role="status">
      <img src={APPEAL_WAITING_GIF} {...playback} alt="Referee reviewing the appeal" className="appeal-waiting-gif" />
      <div className="appeal-waiting-caption">Ref is taking a closer look...</div>
    </div>
  );
}
