import { useState } from "react";
import { useParams } from "react-router-dom";
import { useReviewSession } from "../hooks/useReviewSession";
import { VarIntro } from "../components/VarIntro";
import { FindingReview } from "../components/FindingReview";
import { CardBadge } from "../components/CardBadge";
import { HpBar } from "../components/HpBar";
import { submitAppeal, continuePush } from "../lib/api";

export function ReviewPage() {
  const { sessionId = "" } = useParams();
  const { session, error } = useReviewSession(sessionId);
  const [introDone, setIntroDone] = useState(false);
  const [skip, setSkip] = useState(false);
  const [pendingAppealFindingId, setPendingAppealFindingId] = useState<string | null>(null);
  const [submittedAppealFindingIds, setSubmittedAppealFindingIds] = useState<Set<string>>(new Set());
  const [continuing, setContinuing] = useState(false);

  if (error) {
    return (
      <div className="page-center">
        <div className="error-box">Could not load review session: {error}</div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="page-center">
        <div className="loading">Loading review session...</div>
      </div>
    );
  }

  const isReviewing = session.status === "collecting" || session.status === "reviewing";
  const showIntro = !introDone && !skip;

  const handleContest = async (findingId: string, text: string) => {
    if (submittedAppealFindingIds.has(findingId)) return;
    setSubmittedAppealFindingIds((prev) => new Set(prev).add(findingId));
    setPendingAppealFindingId(findingId);
    try {
      await submitAppeal(sessionId, findingId, text);
    } catch (e) {
      // Submission failed before the backend accepted it — allow retrying.
      setSubmittedAppealFindingIds((prev) => {
        const next = new Set(prev);
        next.delete(findingId);
        return next;
      });
    } finally {
      setPendingAppealFindingId(null);
    }
  };

  const handleContinue = async () => {
    setContinuing(true);
    try {
      await continuePush(sessionId);
    } finally {
      setContinuing(false);
    }
  };

  const noFindings = session.findings.length === 0 && session.status !== "reviewing" && session.status !== "collecting";
  const isTerminal = session.status === "approved" || session.status === "blocked";
  const hasUnresolvedRed = session.findings.some(
    (f) => f.severity === "red" && !session.appeals.some((a) => a.finding_id === f.id && a.outcome === "overturned"),
  );

  return (
    <div className="review-page">
      <header className="review-header">
        <div className="review-meta">
          <span className="repo-tag">{session.repo}</span>
          <span className="branch-tag">{session.branch}</span>
        </div>
        <HpBar hpBefore={session.hp_before} hpAfter={session.hp_after} />
      </header>

      {showIntro ? (
        <VarIntro onDone={() => setIntroDone(true)} skip={skip} />
      ) : (
        <>
          {!skip && !isTerminal && (
            <button className="btn btn-skip" onClick={() => setSkip(true)}>
              Skip animation / Show result
            </button>
          )}

          {isReviewing && (
            <div className="reviewing-banner">
              <div className="spinner" />
              CHECKING FOR SLOP...
            </div>
          )}

          {noFindings && (
            <div className="play-on-banner">
              <CardBadge severity="play_on" />
              <p>No actionable issues found. Clean run.</p>
            </div>
          )}

          <div className="findings-list">
            {session.findings.map((finding) => {
              const appeal = session.appeals.find((a) => a.finding_id === finding.id);
              return (
                <FindingReview
                  key={finding.id}
                  finding={finding}
                  diff={session.diff}
                  skip={skip}
                  appeal={appeal}
                  appealPending={pendingAppealFindingId === finding.id}
                  appealSubmitted={submittedAppealFindingIds.has(finding.id)}
                  onContest={handleContest}
                />
              );
            })}
          </div>

          {!isReviewing && !isTerminal && !hasUnresolvedRed && (
            <div className="continue-bar">
              <button className="btn btn-continue" onClick={handleContinue} disabled={continuing}>
                {continuing ? "Continuing..." : "Continue Push"}
              </button>
            </div>
          )}

          {session.status === "approved" && (
            <div className="terminal-banner terminal-approved">PUSH ALLOWED — the waiting `git push` will now continue.</div>
          )}
          {session.status === "blocked" && (
            <div className="terminal-banner terminal-blocked">PUSH BLOCKED — the waiting `git push` has been stopped.</div>
          )}
        </>
      )}
    </div>
  );
}
