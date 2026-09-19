import type { Evidence } from "../lib/types";

const TYPE_LABELS: Record<string, string> = {
  test: "TEST",
  lint: "LINT",
  repo_context: "REPO",
  git_history: "HISTORY",
  runtime: "RUNTIME",
};

export function EvidenceList({ evidence }: { evidence: Evidence[] }) {
  if (!evidence.length) return null;
  return (
    <div className="evidence-list">
      <span className="eyebrow">Evidence</span>
      <ul>
        {evidence.map((e, i) => {
          const pips = Math.max(1, Math.min(5, Math.round(e.strength * 5)));
          return (
            <li key={i} className="evidence-item">
              <span className="evidence-tag">{TYPE_LABELS[e.type] ?? e.type}</span>
              <span className="evidence-summary">{e.summary}</span>
              <span className="evidence-strength" title={`strength ${e.strength}`} aria-label={`strength ${pips} of 5`}>
                {[0, 1, 2, 3, 4].map((p) => (
                  <span key={p} className={`pip ${p < pips ? "pip-on" : ""}`} />
                ))}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
