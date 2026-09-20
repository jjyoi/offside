import type { Appeal, Finding } from "../lib/types";

interface Props {
  findings: Finding[];
  appeals: Appeal[];
  activeIndex: number;
  revealedIds: Set<string>;
  onSelect: (index: number) => void;
}

function statusFor(finding: Finding, appeals: Appeal[], revealed: boolean): string {
  if (finding.fix_decision === "accepted") return "Fix accepted";
  if (finding.fix_decision === "declined") return "Conceded";
  const appeal = appeals.find((a) => a.finding_id === finding.id);
  if (appeal?.outcome === "overturned") return "Overturned";
  if (appeal?.outcome === "downgraded") return "Downgraded";
  if (appeal?.outcome === "stands") return "Stands";
  return revealed ? "Reviewed" : "Pending";
}

export function FindingsOverview({ findings, appeals, activeIndex, revealedIds, onSelect }: Props) {
  if (findings.length < 2) return null;

  const reviewedCount = findings.filter((f) => revealedIds.has(f.id)).length;

  return (
    <nav className="overview" aria-label="All findings">
      <span className="eyebrow">
        {findings.length} incidents · {reviewedCount} reviewed
      </span>
      <ol className="overview-list">
        {findings.map((finding, index) => {
          const revealed = revealedIds.has(finding.id);
          const status = statusFor(finding, appeals, revealed);
          return (
            <li key={finding.id}>
              <button
                type="button"
                className={`overview-item ${index === activeIndex ? "is-active" : ""}`}
                aria-current={index === activeIndex ? "step" : undefined}
                onClick={() => onSelect(index)}
              >
                <span className={`booking-chip booking-chip-${finding.severity}`} aria-hidden="true" />
                <span className="overview-file">
                  {finding.file}:{finding.start_line}
                </span>
                <span className="overview-category">{finding.category}</span>
                <span className="overview-status">{status}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
