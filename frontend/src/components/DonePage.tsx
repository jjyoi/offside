import { motion } from "motion/react";
import type { Finding, ReviewSession } from "../lib/types";
import { HpBar } from "./HpBar";

interface Props {
  session: ReviewSession;
  hpAfter: number;
  blocked: boolean;
}

function acceptedFixes(findings: Finding[]): Finding[] {
  return findings.filter((f) => f.fix_decision === "accepted" && f.suggested_fix);
}

function blockers(findings: Finding[], appeals: ReviewSession["appeals"]): Finding[] {
  return findings.filter((f) => {
    if (f.severity !== "red") return false;
    if (f.fix_decision === "accepted") return false;
    const overturned = appeals.some((a) => a.finding_id === f.id && a.outcome === "overturned");
    return !overturned;
  });
}

function conceded(findings: Finding[]): Finding[] {
  return findings.filter((f) => f.fix_decision === "declined");
}

export function DonePage({ session, hpAfter, blocked }: Props) {
  const fixes = acceptedFixes(session.findings);
  const stillBlocking = blocked ? blockers(session.findings, session.appeals) : [];
  const declined = blocked ? conceded(session.findings) : [];
  const outOfHp = hpAfter <= 0;

  return (
    <motion.div
      className={`done-page ${blocked ? "done-page-blocked" : "done-page-approved"}`}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className={`done-stamp ${blocked ? "done-stamp-blocked" : "done-stamp-approved"}`}>
        {blocked ? "PUSH BLOCKED" : "PUSH ALLOWED"}
      </div>

      <p className="done-subtitle">
        {blocked
          ? outOfHp
            ? "Out of HP — the waiting `git push` has been stopped."
            : "A red card is still standing — the waiting `git push` has been stopped."
          : "The waiting `git push` will now continue."}
      </p>

      <div className="done-hp">
        <HpBar hpBefore={session.hp_before} hpAfter={hpAfter} />
      </div>

      {blocked && stillBlocking.length > 0 && (
        <div className="done-section done-section-blockers">
          <span className="eyebrow">Still blocking</span>
          <ul className="done-list">
            {stillBlocking.map((f) => (
              <li key={f.id} className="done-list-item">
                <span className="booking-chip booking-chip-red" aria-hidden="true" />
                <span className="done-list-location">
                  {f.file}:{f.start_line}
                </span>
                <span className="done-list-note">{f.explanation}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {blocked && declined.length > 0 && (
        <div className="done-section done-section-blockers">
          <span className="eyebrow">Conceded, no fix agreed</span>
          <ul className="done-list">
            {declined.map((f) => (
              <li key={f.id} className="done-list-item">
                <span className="booking-chip booking-chip-red" aria-hidden="true" />
                <span className="done-list-location">
                  {f.file}:{f.start_line}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {fixes.length > 0 && (
        <div className="done-section">
          <span className="eyebrow">
            {blocked
              ? "Fixes you already accepted"
              : "Before you push again: fixes you accepted"}
          </span>
          <p className="done-section-note">
            These weren't part of this push. Apply them in your next commit.
          </p>
          <ul className="done-list">
            {fixes.map((f) => (
              <li key={f.id} className="done-list-item done-list-item-fix">
                <span className={`booking-chip booking-chip-${f.severity}`} aria-hidden="true" />
                <div className="done-fix-body">
                  <span className="done-list-location">
                    {f.file}:{f.start_line}
                  </span>
                  <p className="done-fix-text">{f.suggested_fix}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!blocked && fixes.length === 0 && (
        <p className="done-clean-note">No outstanding fixes — nothing else to do before your next push.</p>
      )}
    </motion.div>
  );
}
