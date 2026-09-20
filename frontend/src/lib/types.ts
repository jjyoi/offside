export type ReviewStatus =
  | "collecting"
  | "reviewing"
  | "awaiting_appeal"
  | "approved"
  | "blocked";

export type ExplanationLevel = "intern" | "mid" | "staff" | "messi" | "ronaldo" | "son";

export type FixDecision = "accepted" | "declined";

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
  suggested_fix: string;
  hp_delta: number;
  appeal_penalty: number;
  fix_decision?: FixDecision | null;
  evidence: Evidence[];
}

export type AppealOutcome = "overturned" | "downgraded" | "stands";

export interface Appeal {
  id: string;
  finding_id: string;
  text: string;
  transcript?: string | null;
  claimed_hypothesis?: string | null;
  second_pass_evidence: Evidence[];
  outcome?: AppealOutcome | null;
  downgraded_severity?: Severity | null;
  hp_delta_before_downgrade?: number | null;
  hp_penalty?: number;
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
  repo_path?: string | null;
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
