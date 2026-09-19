export type ReviewStatus =
  | "collecting"
  | "reviewing"
  | "awaiting_appeal"
  | "approved"
  | "blocked";

export type Severity = "play_on" | "yellow" | "red";

export type EvidenceType = "test" | "lint" | "repo_context" | "git_history" | "runtime";

export interface Evidence {
  type: EvidenceType;
  summary: string;
  source_ref?: string | null;
  strength: number;
}

export interface Finding {
  id: string;
  file: string;
  start_line: number;
  end_line: number;
  category: string;
  severity: Severity;
  confidence: number;
  explanation: string;
  roast: string;
  hp_delta: number;
  evidence: Evidence[];
}

export type AppealOutcome = "overturned" | "stands";

export interface Appeal {
  id: string;
  finding_id: string;
  text: string;
  transcript?: string | null;
  claimed_hypothesis?: string | null;
  second_pass_evidence: Evidence[];
  outcome?: AppealOutcome | null;
  created_at: number;
}

export interface ReviewEvent {
  id: string;
  type: string;
  data: Record<string, unknown>;
  created_at: number;
}

export interface ReviewSession {
  id: string;
  repo: string;
  branch: string;
  local_sha: string;
  remote_sha?: string | null;
  diff: string;
  commits: string[];
  author?: string | null;
  status: ReviewStatus;
  hp_before: number;
  hp_after: number;
  findings: Finding[];
  appeals: Appeal[];
  timeline: ReviewEvent[];
  created_at: number;
  updated_at: number;
}
