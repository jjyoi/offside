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
      <div className="evidence-heading">Evidence</div>
      <ul>
        {evidence.map((e, i) => (
          <li key={i} className="evidence-item">
            <span className="evidence-tag">{TYPE_LABELS[e.type] ?? e.type}</span>
            <span className="evidence-summary">{e.summary}</span>
            <span className="evidence-strength" title={`strength ${e.strength}`}>
              {"●".repeat(Math.max(1, Math.round(e.strength * 5)))}
              {"○".repeat(5 - Math.max(1, Math.round(e.strength * 5)))}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
