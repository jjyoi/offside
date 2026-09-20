import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import type { Appeal, Finding } from "../lib/types";
import { DiffReplay } from "./DiffReplay";
import { CardBadge } from "./CardBadge";
import { EvidenceList } from "./EvidenceList";
import { AppealForm } from "./AppealForm";
import { AppealWaiting } from "./AppealWaiting";

type Stage = "diff" | "explanation" | "evidence" | "roast" | "verdict";

interface Props {
  finding: Finding;
  index: number;
  diff: string;
  skip: boolean;
  appeal?: Appeal;
  appealPending: boolean;
  reviewFinished?: boolean;
  appealSubmitted: boolean;
  playerName?: string | null;
  onVerdict: (findingId: string) => void;
  onContest: (findingId: string, text: string) => void;
}

const STAGE_ORDER: Stage[] = ["diff", "explanation", "evidence", "roast", "verdict"];

const fadeUp = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.35, ease: "easeOut" as const },
};

export function FindingReview({
  finding,
  index,
  diff,
  skip,
  appeal: receivedAppeal,
  appealPending,
  appealSubmitted,
  reviewFinished,
  playerName,
  onContest,
  onVerdict,
}: Props) {
  const [resolvedOnMount] = useState(Boolean(receivedAppeal?.outcome));
  const [waitingDone, setWaitingDone] = useState(Boolean(receivedAppeal?.outcome));
  const appeal = appealSubmitted && !waitingDone ? undefined : receivedAppeal;
  const [stageIndex, setStageIndex] = useState(skip || resolvedOnMount ? STAGE_ORDER.length - 1 : 0);
  const stage = STAGE_ORDER[stageIndex];
  const [bookingKey, setBookingKey] = useState(0);
  const bookedOutcome = useRef<string | null>(receivedAppeal?.outcome ? receivedAppeal.id : null);

  useEffect(() => {
    if (appeal?.outcome === "stands" && bookedOutcome.current !== appeal.id) {
      bookedOutcome.current = appeal.id;
      setBookingKey((k) => k + 1);
    }
  }, [appeal]);

  useEffect(() => {
    if (skip) {
      setStageIndex(STAGE_ORDER.length - 1);
    }
  }, [skip]);

  const advance = () => setStageIndex((i) => Math.min(i + 1, STAGE_ORDER.length - 1));

  useEffect(() => {
    if (stage === "diff" || stage === "verdict" || skip) return;
    const timer = setTimeout(advance, stage === "explanation" ? 700 : stage === "evidence" ? 700 : 500);
    return () => clearTimeout(timer);
  }, [stage, skip]);

  useEffect(() => {
    if (stage === "verdict") onVerdict(finding.id);
  }, [stage, finding.id, onVerdict]);

  const overturned = appeal?.outcome === "overturned";

  return (
    <motion.div className="finding-card" {...fadeUp}>
      <div className="finding-header">
        <span className="incident-no">Incident {String(index + 1).padStart(2, "0")}</span>
        <span className="finding-file">
          {finding.file}:{finding.start_line}
          {finding.end_line !== finding.start_line ? `-${finding.end_line}` : ""}
        </span>
        <span className="finding-category">{finding.category}</span>
      </div>

      <DiffReplay
        file={finding.file}
        startLine={finding.start_line}
        endLine={finding.end_line}
        diff={diff}
        onDone={advance}
        skip={skip || resolvedOnMount}
      />

      <AnimatePresence>
        {stageIndex >= 1 && (
          <motion.div className="finding-explanation" key="explanation" {...fadeUp}>
            <span className="eyebrow">The case against it</span>
            <p>{finding.explanation}</p>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {stageIndex >= 2 && (
          <motion.div key="evidence" {...fadeUp}>
            <EvidenceList evidence={finding.evidence} />
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {stageIndex >= 3 && (
          <motion.div className="finding-roast" key="roast" {...fadeUp}>
            <blockquote className="bubble">{finding.roast}</blockquote>
          </motion.div>
        )}
      </AnimatePresence>

      {stageIndex >= 4 && (
        <motion.div
          className="finding-verdict"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
        >
          <div className="card-decision">
            <CardBadge
              severity={overturned ? "play_on" : finding.severity}
              muted={skip || resolvedOnMount}
              suppressGif={resolvedOnMount}
              playerName={appeal?.outcome === "stands" ? playerName : null}
              bookingKey={bookingKey}
              bookingCaption={bookingKey > 0 ? "DECISION STANDS" : undefined}
            />
            {!overturned && finding.hp_delta !== 0 && <div className="hp-delta-tag">{finding.hp_delta} HP</div>}
          </div>

          {overturned && appeal && (
            <div className="appeal-result appeal-overturned">
              <span className="eyebrow">Decision overturned</span>
              <p>{appeal.text}</p>
              <EvidenceList evidence={appeal.second_pass_evidence} />
              <p className="appeal-restored">HP restored.</p>
            </div>
          )}

          {appeal && appeal.outcome === "stands" && (
            <div className="appeal-result appeal-stands">
              <span className="eyebrow">Decision stands</span>
              {appeal.second_pass_evidence.length > 0 ? (
                <>
                  <p className="appeal-note">New evidence gathered:</p>
                  <EvidenceList evidence={appeal.second_pass_evidence} />
                </>
              ) : (
                <p className="appeal-note">
                  No supporting evidence was found in the repository for this claim. The original call stands.
                </p>
              )}
            </div>
          )}

          {finding.severity !== "play_on" && !reviewFinished && !appeal && !appealSubmitted && (
            <AppealForm onSubmit={(text) => onContest(finding.id, text)} disabled={appealPending} />
          )}

          {appealSubmitted && !appeal && <AppealWaiting onDone={() => setWaitingDone(true)} />}
        </motion.div>
      )}
    </motion.div>
  );
}
