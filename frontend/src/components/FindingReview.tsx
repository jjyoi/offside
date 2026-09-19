import { useEffect, useState } from "react";
import type { Appeal, Finding } from "../lib/types";
import { DiffReplay } from "./DiffReplay";
import { CardBadge } from "./CardBadge";
import { EvidenceList } from "./EvidenceList";
import { AppealForm } from "./AppealForm";
import { CoachRunning } from "./CoachRunning";

type Stage = "diff" | "explanation" | "evidence" | "roast" | "verdict";

interface Props {
  finding: Finding;
  diff: string;
  skip: boolean;
  appeal?: Appeal;
  appealPending: boolean;
  appealSubmitted: boolean;
  onContest: (findingId: string, text: string) => void;
}

const STAGE_ORDER: Stage[] = ["diff", "explanation", "evidence", "roast", "verdict"];

export function FindingReview({ finding, diff, skip, appeal, appealPending, appealSubmitted, onContest }: Props) {
  const [stageIndex, setStageIndex] = useState(skip ? STAGE_ORDER.length - 1 : 0);
  const stage = STAGE_ORDER[stageIndex];

  useEffect(() => {
    if (skip) {
      setStageIndex(STAGE_ORDER.length - 1);
    }
  }, [skip]);

  const advance = () => setStageIndex((i) => Math.min(i + 1, STAGE_ORDER.length - 1));

  useEffect(() => {
    if (stage === "diff" || skip) return;
    const timer = setTimeout(advance, stage === "explanation" ? 900 : stage === "evidence" ? 900 : 700);
    return () => clearTimeout(timer);
  }, [stage, skip]);

  const overturned = appeal?.outcome === "overturned";

  return (
    <div className="finding-card">
      <div className="finding-header">
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
        skip={skip}
      />

      {stageIndex >= 1 && (
        <div className="finding-explanation">
          <div className="section-heading">The Case Against It</div>
          <p>{finding.explanation}</p>
        </div>
      )}

      {stageIndex >= 2 && <EvidenceList evidence={finding.evidence} />}

      {stageIndex >= 3 && (
        <div className="finding-roast">
          <div className="section-heading">Commentary</div>
          <p>&ldquo;{finding.roast}&rdquo;</p>
        </div>
      )}

      {stageIndex >= 4 && (
        <div className="finding-verdict">
          <CardBadge severity={overturned ? "play_on" : finding.severity} />
          {!overturned && finding.hp_delta !== 0 && <div className="hp-delta-tag">{finding.hp_delta} HP</div>}

          {overturned && appeal && (
            <div className="appeal-result appeal-overturned">
              <div className="section-heading">DECISION OVERTURNED</div>
              <p>{appeal.text}</p>
              <EvidenceList evidence={appeal.second_pass_evidence} />
              <p className="appeal-restored">HP restored.</p>
            </div>
          )}

          {appeal && appeal.outcome === "stands" && (
            <div className="appeal-result appeal-stands">
              <div className="section-heading">DECISION STANDS</div>
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

          {finding.severity !== "play_on" && !appeal && !appealSubmitted && (
            <AppealForm onSubmit={(text) => onContest(finding.id, text)} disabled={appealPending} />
          )}

          {appealSubmitted && !appeal && <CoachRunning />}
        </div>
      )}
    </div>
  );
}
