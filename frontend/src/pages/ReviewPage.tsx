import { useCallback, useState } from "react";
import { useParams } from "react-router-dom";
import { useReviewSession } from "../hooks/useReviewSession";
import { VarIntro } from "../components/VarIntro";
import { FindingReview } from "../components/FindingReview";
import { CardBadge } from "../components/CardBadge";
import { HpBar } from "../components/HpBar";
import { BookingsTracker } from "../components/BookingsTracker";
import { submitAppeal, continuePush } from "../lib/api";

export function ReviewPage() {
  const { sessionId = "" } = useParams();
  return <ReviewSessionPage key={sessionId} sessionId={sessionId} />;
}

function ReviewSessionPage({ sessionId }: { sessionId: string }) {
  const { session, error } = useReviewSession(sessionId);
  const [introDone, setIntroDone] = useState(false);
  const [skip, setSkip] = useState(false);
  const [pendingAppealFindingId, setPendingAppealFindingId] = useState<string | null>(null);
  const [submittedAppealFindingIds, setSubmittedAppealFindingIds] = useState<Set<string>>(new Set());
  const [continuing, setContinuing] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [revealedIds, setRevealedIds] = useState<Set<string>>(new Set());
  const handleVerdict = useCallback((id: string) => {
    setRevealedIds((previous) => previous.has(id) ? previous : new Set(previous).add(id));
  }, []);

  if (error) {
    return (
      <div className="page-center">
        <div className="poster poster-error" role="alert">
          <h1 className="poster-title">Abandoned match</h1>
          <p>Could not load review session: {error}</p>
        </div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="page-center">
        <div className="poster">
          <div className="ball" aria-hidden="true" />
          <h1 className="poster-title">Warming up</h1>
          <p>Loading review session...</p>
        </div>
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
    } catch {
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

  const currentFinding = session.findings[activeIndex];
  const displayedHp = Math.max(0, session.hp_before + session.findings.reduce((total, finding) => {
    const overturned = session.appeals.some((appeal) => appeal.finding_id === finding.id && appeal.outcome === "overturned");
    return total + (revealedIds.has(finding.id) && !overturned ? finding.hp_delta : 0);
  }, 0));
  const allRevealed = session.findings.every((finding) => revealedIds.has(finding.id));

  return (
    <div className="review-page">
      <header className="scoreboard">
        <div className="wordmark">
          Offside <span className="wordmark-var">VAR</span>
        </div>
        <div className="fixture">
          <span className="team" title={session.repo}>{session.repo}</span>
          <span className="fixture-vs">v</span>
          <span className="team" title={session.branch}>{session.branch}</span>
        </div>
        <HpBar hpBefore={session.hp_before} hpAfter={displayedHp} />
      </header>

      {showIntro ? (
        <VarIntro onDone={() => setIntroDone(true)} skip={skip} />
      ) : (
        <>
          {!skip && !isTerminal && currentFinding && !revealedIds.has(currentFinding.id) && (
            <button className="btn btn-skip" onClick={() => setSkip(true)}>
              Skip this animation
            </button>
          )}

          {isReviewing && (
            <div className="reviewing-banner">
              <div className="ball" aria-hidden="true" />
              Checking for slop...
            </div>
          )}

          {noFindings && (
            <div className="play-on-banner">
              <CardBadge severity="play_on" />
              <p>No actionable issues found. Clean run. Play on.</p>
            </div>
          )}

          <div className="findings-list">
            {session.findings.slice(activeIndex, activeIndex + 1).map((finding) => {
              const appeal = session.appeals.find((a) => a.finding_id === finding.id);
              return (
                <FindingReview
                  key={finding.id}
                  finding={finding}
                  index={activeIndex}
                  diff={session.diff}
                  skip={skip || revealedIds.has(finding.id)}
                  onVerdict={handleVerdict}
                  appeal={appeal}
                  appealPending={pendingAppealFindingId === finding.id}
                  appealSubmitted={submittedAppealFindingIds.has(finding.id)}
                  playerName={session.author}
                  onContest={handleContest}
                />
              );
            })}
          </div>

          {currentFinding && (
            <nav className="finding-navigation" aria-label="Review findings">
              <button className="btn" disabled={activeIndex === 0} onClick={() => { setSkip(false); setActiveIndex((index) => index - 1); }}>
                Previous issue
              </button>
              <span>Issue {activeIndex + 1} of {session.findings.length}</span>
              <button className="btn" disabled={!revealedIds.has(currentFinding.id) || activeIndex >= session.findings.length - 1}
                onClick={() => { setSkip(false); setActiveIndex((index) => index + 1); }}>
                Next issue
              </button>
            </nav>
          )}

          {!isReviewing && !isTerminal && !hasUnresolvedRed && allRevealed && (
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

          <BookingsTracker
            findings={session.findings}
            appeals={session.appeals}
            playerName={session.author}
            revealedIds={revealedIds}
          />
        </>
      )}
    </div>
  );
}
