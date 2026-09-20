import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ContestIntro } from "./ContestIntro";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";

interface Props {
  onSubmit: (text: string) => void;
  disabled?: boolean;
  /** HP gained if the contest wins and lost if it fails, shown so it reads as a real bet. */
  stakes?: { win: number; lose: number };
}

type Phase = "idle" | "intro" | "form";

const TIME_LIMIT_SECONDS = 60;

export function AppealForm({ onSubmit, disabled, stakes }: Props) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [text, setText] = useState("");
  const [secondsLeft, setSecondsLeft] = useState(TIME_LIMIT_SECONDS);
  const textRef = useRef(text);
  textRef.current = text;

  const { start, stop, listening, interimText, supported } = useSpeechRecognition((chunk) => {
    if (!chunk) return;
    setText((prev) => (prev ? `${prev.trim()} ${chunk}` : chunk));
  });

  useEffect(() => {
    if (phase !== "form") return;
    if (secondsLeft <= 0) {
      stop();
      onSubmit(textRef.current.trim() || "(no argument given before time ran out)");
      return;
    }
    const timer = setTimeout(() => setSecondsLeft((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [phase, secondsLeft, onSubmit, stop]);

  const submit = () => {
    if (!text.trim()) return;
    stop();
    onSubmit(text.trim());
  };

  const minutes = Math.floor(secondsLeft / 60);
  const seconds = secondsLeft % 60;
  const urgent = secondsLeft <= 10;

  if (phase === "idle") {
    return (
      <div className="contest-trigger">
        <button
          type="button"
          className="btn btn-contest btn-contest-trigger"
          disabled={disabled}
          onClick={() => setPhase("intro")}
        >
          Contest Decision
        </button>
        {stakes && <Stakes {...stakes} />}
      </div>
    );
  }

  return (
    <>
      <AnimatePresence>
        {phase === "intro" && <ContestIntro onDone={() => setPhase("form")} />}
      </AnimatePresence>

      {phase === "form" && (
        <motion.form
          className="appeal-form"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <div className="appeal-form-header">
            <label className="eyebrow" htmlFor="appeal-text">
              Think the ref got it wrong?
            </label>
            <span className={`appeal-timer ${urgent ? "appeal-timer-urgent" : ""}`}>
              {minutes}:{String(seconds).padStart(2, "0")}
            </span>
          </div>

          <div className="appeal-input-row">
            <textarea
              id="appeal-text"
              placeholder="Make your case. e.g. 'The caller already enforces a 10-second timeout.'"
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={disabled}
              rows={3}
              autoFocus
            />
            {supported && (
              <button
                type="button"
                className={`mic-btn ${listening ? "mic-btn-active" : ""}`}
                onClick={() => (listening ? stop() : start())}
                disabled={disabled}
                aria-label={listening ? "Stop recording" : "Record your argument"}
                title={listening ? "Stop recording" : "Record your argument"}
              >
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                  <path
                    d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z"
                    stroke="currentColor"
                    strokeWidth="1.6"
                  />
                  <path
                    d="M6 11a6 6 0 0 0 12 0M12 19v2"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                  />
                </svg>
                {listening && <span className="mic-pulse" aria-hidden="true" />}
              </button>
            )}
          </div>

          {listening && (
            <div className="mic-status">
              {interimText ? <em>{interimText}</em> : "Listening..."}
            </div>
          )}

          {stakes && <Stakes {...stakes} />}

          <button type="submit" className="btn btn-contest" disabled={disabled || !text.trim()}>
            Submit Appeal
          </button>
        </motion.form>
      )}
    </>
  );
}

function Stakes({ win, lose }: { win: number; lose: number }) {
  return (
    <p className="contest-stakes">
      Win it: <span className="stake-win">+{win} HP</span>
      <span aria-hidden="true"> · </span>
      Lose it: <span className="stake-lose">−{lose} HP</span>
    </p>
  );
}
