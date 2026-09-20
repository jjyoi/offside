import { useCallback, useState } from "react";
import type { FixDecision } from "../lib/types";
import { useParams } from "react-router-dom";
import { useReviewSession } from "../hooks/useReviewSession";
import { VarIntro } from "../components/VarIntro";
import { FindingReview } from "../components/FindingReview";
import { CardBadge } from "../components/CardBadge";
import { HpBar } from "../components/HpBar";
import { BookingsTracker } from "../components/BookingsTracker";
import { FindingsOverview } from "../components/FindingsOverview";
import { SettingsButton } from "../components/SettingsButton";
import { DonePage } from "../components/DonePage";
import { submitAppeal, continuePush, decideFix } from "../lib/api";

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
  const [completionError, setCompletionError] = useState<string | null>(null);
  const [completedStatus, setCompletedStatus] = useState<"approved" | "blocked" | null>(null);
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

  const handleFixDecision = async (findingId: string, decision: FixDecision) => {
    try {
      await decideFix(sessionId, findingId, decision);
    } catch {
      // The session refetches on events; a failed call just leaves the buttons available to retry.
    }
  };

  const handleContinue = async () => {
    setContinuing(true);
    setCompletionError(null);
    try {
      const result = await continuePush(sessionId);
      setCompletedStatus(result.status);
    } catch {
      setCompletionError("Could not finish the review. Please try again.");
    } finally {
      setContinuing(false);
    }
  };

  const noFindings = session.findings.length === 0 && session.status !== "reviewing" && session.status !== "collecting";
  const finalStatus = completedStatus ?? session.status;
  const isTerminal = finalStatus === "approved" || finalStatus === "blocked";
  const appealInProgress = pendingAppealFindingId !== null || [...submittedAppealFindingIds].some(
    (id) => !session.appeals.some((appeal) => appeal.finding_id === id && appeal.outcome),
  );
  const hasUnresolvedRed = session.findings.some(
    (f) =>
      f.severity === "red" &&
      f.fix_decision !== "accepted" &&
      !session.appeals.some((a) => a.finding_id === f.id && a.outcome === "overturned"),
  );

  const currentFinding = session.findings[activeIndex];
  const displayedHp = Math.min(100, session.hp_before + session.findings.reduce((total, finding) => {
    const overturned = session.appeals.some((appeal) => appeal.finding_id === finding.id && appeal.outcome === "overturned");
    if (!revealedIds.has(finding.id) || overturned) return total;
    const refund = finding.fix_decision === "accepted" ? Math.floor(Math.abs(finding.hp_delta) / 2) : 0;
    return total + finding.hp_delta + refund;
  }, 0) + session.appeals.reduce((total, appeal) => total + (revealedIds.has(appeal.finding_id) ? appeal.hp_penalty ?? 0 : 0), 0));
  const isLast = activeIndex >= session.findings.length - 1;
  const currentRevealed = currentFinding ? revealedIds.has(currentFinding.id) : false;
  const pushBlocked = hasUnresolvedRed || displayedHp <= 0;
  const allRevealed = session.findings.every((finding) => revealedIds.has(finding.id));
  const playerName = session.author || "YOU";

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
        {!isTerminal && <HpBar hpBefore={session.hp_before} hpAfter={displayedHp} />}
        <SettingsButton />
      </header>

      {showIntro ? (
        <VarIntro onDone={() => setIntroDone(true)} skip={skip} />
      ) : isTerminal ? (
        // Use the backend's authoritative hp_after here, not the reveal-gated displayedHp:
        // a done page can be the first thing rendered (e.g. reopening the review link after
        // the fact), when revealedIds is still empty and would otherwise show a stale 100.
        <DonePage session={session} hpAfter={session.hp_after} blocked={finalStatus === "blocked"} />
      ) : (
        <>
          {!skip && currentFinding && !revealedIds.has(currentFinding.id) && (
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

          <FindingsOverview
            findings={session.findings}
            appeals={session.appeals}
            activeIndex={activeIndex}
            revealedIds={revealedIds}
            onSelect={(index) => {
              // Jumping ahead means the ones skipped over are accepted as read.
              session.findings.slice(0, index).forEach((f) => handleVerdict(f.id));
              setSkip(false);
              setActiveIndex(index);
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
          />

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
                  reviewFinished={continuing}
                  playerName={playerName}
                  onContest={handleContest}
                  onFixDecision={handleFixDecision}
                />
              );
            })}
          </div>

          {currentFinding && (
            <nav className="finding-navigation" aria-label="Review findings">
              <button className="btn" disabled={activeIndex === 0} onClick={() => { setSkip(false); setActiveIndex((index) => index - 1); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
                Previous issue
              </button>
              <span>Issue {activeIndex + 1} of {session.findings.length}</span>
              <button className="btn" disabled={isLast && currentRevealed}
                onClick={() => {
                  // "Yeah, we get it": count this call as seen and move on, contested or not.
                  handleVerdict(currentFinding.id);
                  if (!isLast) { setSkip(false); setActiveIndex((index) => index + 1); }
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}>
                {isLast && !currentRevealed ? "Skip to verdict" : "Next issue"}
              </button>
            </nav>
          )}

          {!isReviewing && allRevealed && (
            <div className="continue-bar">
              {displayedHp <= 0 ? (
                <p className="continue-note">Out of HP. With none left the push is blocked, unless you win a contest.</p>
              ) : hasUnresolvedRed ? (
                <p className="continue-note">A red card stops the push. Contest it, accept its fix, or concede.</p>
              ) : null}
              <button className={`btn ${pushBlocked ? "btn-block" : "btn-continue"}`} onClick={handleContinue} disabled={continuing || appealInProgress}>
                {continuing ? "Finishing review..." : appealInProgress ? "Waiting for appeal..." : pushBlocked ? "Accept verdict / Block push" : "Continue Push"}
              </button>
            </div>
          )}

          {completionError && <div className="terminal-banner terminal-blocked" role="alert">{completionError}</div>}

          <BookingsTracker
            findings={session.findings}
            appeals={session.appeals}
            playerName={playerName}
            revealedIds={revealedIds}
            activeId={currentFinding?.id}
            onSelect={(index) => { setSkip(false); setActiveIndex(index); window.scrollTo({ top: 0, behavior: "smooth" }); }}
          />
        </>
      )}
    </div>
  );
}
