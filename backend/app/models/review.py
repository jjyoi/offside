from __future__ import annotations

import time
import uuid
from enum import Enum

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ReviewStatus(str, Enum):
    collecting = "collecting"
    reviewing = "reviewing"
    awaiting_appeal = "awaiting_appeal"
    approved = "approved"
    blocked = "blocked"


class ExplanationLevel(str, Enum):
    intern = "intern"
    mid = "mid"
    staff = "staff"


class Severity(str, Enum):
    play_on = "play_on"
    yellow = "yellow"
    red = "red"


class EvidenceType(str, Enum):
    test = "test"
    lint = "lint"
    repo_context = "repo_context"
    git_history = "git_history"
    runtime = "runtime"


class Evidence(BaseModel):
    type: EvidenceType
    summary: str
    source_ref: str | None = None
    strength: float = Field(ge=0, le=1)


class FixDecision(str, Enum):
    accepted = "accepted"
    declined = "declined"


class Finding(BaseModel):
    id: str = Field(default_factory=lambda: new_id("finding"))

    file: str
    start_line: int
    end_line: int

    category: str
    severity: Severity
    confidence: float = Field(ge=0, le=1)

    explanation: str
    roast: str
    suggested_fix: str = ""

    hp_delta: int = 0
    # Extra HP lost if the developer contests this call and loses. Scales with the ref's confidence.
    appeal_penalty: int = 0
    fix_decision: FixDecision | None = None

    evidence: list[Evidence] = Field(default_factory=list)


class AppealOutcome(str, Enum):
    overturned = "overturned"
    downgraded = "downgraded"
    stands = "stands"


class Appeal(BaseModel):
    id: str = Field(default_factory=lambda: new_id("appeal"))
    finding_id: str
    text: str
    transcript: str | None = None

    claimed_hypothesis: str | None = None
    second_pass_evidence: list[Evidence] = Field(default_factory=list)

    outcome: AppealOutcome | None = None
    # Set only when outcome == downgraded: the card's new severity (always yellow today),
    # plus the HP the finding was costing right before the downgrade, so the browser can
    # show how much ground was recovered without needing to remember the original card.
    downgraded_severity: Severity | None = None
    hp_delta_before_downgrade: int | None = None
    hp_penalty: int = 0  # negative; HP lost for a failed challenge
    created_at: float = Field(default_factory=time.time)


class ReviewEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("evt"))
    type: str
    data: dict = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)


class ReviewSession(BaseModel):
    id: str = Field(default_factory=lambda: new_id("review"))
    repo: str
    branch: str
    local_sha: str
    remote_sha: str | None = None
    diff: str
    commits: list[str] = Field(default_factory=list)
    author: str | None = None
    level: ExplanationLevel = ExplanationLevel.mid

    status: ReviewStatus = ReviewStatus.collecting

    hp_before: int = 100
    hp_after: int = 100

    findings: list[Finding] = Field(default_factory=list)
    appeals: list[Appeal] = Field(default_factory=list)
    timeline: list[ReviewEvent] = Field(default_factory=list)

    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
