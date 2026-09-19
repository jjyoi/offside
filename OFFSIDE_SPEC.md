# Offside — Technical Implementation Specification

> **Source of truth for implementation.** Read this file fully before writing code. Build the MVP in the order defined below. Do not add sponsor integrations or stretch features until the core push → review → verdict → appeal flow works end to end.

## 1. Product Summary

**Offside** is a Git pre-push referee.

When a developer runs `git push`, Offside pauses the push, inspects the outgoing diff, gathers evidence, and opens a browser-based VAR review. Suspicious code is replayed line-by-line, receives a technical explanation plus a roast, and may be given a yellow or red card with an HP deduction. The developer can contest the call using text or voice; Offside then performs a deeper second-pass investigation before allowing or blocking the push.

**Design principle:** do not build an LLM code reviewer with a football skin. Build a referee that investigates whether the code is actually guilty.

### Core demo loop

```text
git push
  ↓
pre-push hook
  ↓
Offside CLI collects outgoing diff + local evidence
  ↓
review session created
  ↓
browser opens automatically
  ↓
VAR animation
  ↓
flagged lines are replayed / typed out
  ↓
technical finding + roast + card + HP deduction
  ↓
optional contest
  ↓
deeper evidence gathering
  ↓
decision overturned or stands
  ↓
push continues or is blocked
```

## 2. Goals

The MVP must:

1. Intercept a local `git push` with a Git `pre-push` hook.
2. Determine the exact commits/diff about to be pushed.
3. Create a review session and open a browser page automatically.
4. Run deterministic checks plus an LLM-based first-pass review.
5. Show an animated VAR review with flagged code, evidence, roast, severity, and HP.
6. Let the developer contest a finding in text.
7. Perform a deeper second-pass review using the developer's argument as a hypothesis to verify.
8. Return a final verdict to the waiting Git process.
9. Exit `0` to allow the push or non-zero to block it.
10. Require no manual backend intervention during the demo.

## 3. Non-Goals for the Hackathon MVP

Do **not** spend early build time on:

- automatic GitHub branch protection
- organization-wide authentication
- perfect repository indexing
- multi-repository dashboards
- advanced team leaderboards
- production-grade sandboxing
- dozens of static-analysis integrations
- perfect voice transcription
- automatic browser testing for every repository
- every sponsor integration

Local hooks can be bypassed with `git push --no-verify`; this is acceptable for the hackathon. A real product can later add a required GitHub status check.

## 4. Recommended Stack

Use the simplest stack the team can ship quickly.

- **CLI / hook:** Python or Node.js
- **Backend:** FastAPI or Express
- **Frontend:** React / Next.js / Vite
- **Realtime updates:** Server-Sent Events or WebSockets
- **Model inference:** Baseten
- **Optional repo/context store:** Elasticsearch only if it becomes useful
- **Optional runtime verification:** Browserbase

Prefer boring infrastructure over clever infrastructure.

## 5. System Architecture

```text
                          git push
                              │
                              ▼
                       [pre-push hook]
                              │
                              ▼
                         [Offside CLI]
                    collect refs / diff / metadata
                              │
              ┌───────────────┼─────────────────┐
              │               │                 │
              ▼               ▼                 ▼
       deterministic      create review      open browser
          checks             session           session URL
              │               │                 │
              └───────────────┼─────────────────┘
                              ▼
                          [Backend]
                              │
                    reviewer / tool loop
                              │
              ┌───────────────┼─────────────────┐
              ▼               ▼                 ▼
          repo context     model inference   optional tools
             search          (Baseten)       Browserbase etc.
              │               │                 │
              └───────────────┼─────────────────┘
                              ▼
                         session state
                          /         \
                         /           \
                 [Browser UI]     [Offside CLI]
                      │                │
                live updates      waits for final
                                       │
                           ┌───────────┴───────────┐
                           ▼                       ▼
                        exit 0                  exit 1
                           │                       │
                    push continues            push blocked
```

The backend is the source of truth for each review session. The browser UI and CLI observe the same session state.

## 6. Git Hook and CLI

### 6.1 Pre-push hook

Install a small hook at `.git/hooks/pre-push`, or configure `core.hooksPath` for a cleaner installer.

The hook itself should do almost nothing:

```sh
#!/bin/sh
offside pre-push "$@"
exit $?
```

The CLI should read the refs provided to the `pre-push` hook and determine the outgoing range.

Typical branch case:

```sh
git diff <remote-sha>..<local-sha>
git log <remote-sha>..<local-sha> --oneline
```

Handle new branches and missing remote SHAs explicitly rather than assuming the normal case.

### 6.2 Browser gate

After creating a review session:

```text
POST /api/reviews
→ { sessionId, reviewUrl }
```

The CLI opens:

```text
http://localhost:3000/review/<session-id>
```

On macOS:

```sh
open "http://localhost:3000/review/<session-id>"
```

Then the CLI waits for the backend to reach a terminal state.

Pseudo-code:

```python
session = create_review(diff, metadata)
open_browser(session.review_url)

while True:
    status = wait_for_status(session.id)

    if status == "approved":
        raise SystemExit(0)

    if status == "blocked":
        raise SystemExit(1)
```

Use a hard timeout. Never strand the user in an unkillable `git push`.

## 7. Review Pipeline

### 7.1 First principle

Do not send only the raw diff to one model and trust its answer.

The first-pass model should identify a **possible offence** and, where necessary, request evidence before producing a final card.

### 7.2 Pipeline

```text
OUTGOING DIFF
    │
    ▼
cheap deterministic checks
- lint
- relevant tests
- typecheck
- complexity / security check if available
    │
    ▼
fast referee pass
    │
    ├── confident clean ───────────────► PLAY ON
    │
    └── suspicious / uncertain
                 │
                 ▼
          investigation tools
          - inspect nearby code
          - inspect callers/callees
          - search similar call sites
          - inspect tests
          - inspect git history / blame
          - inspect docs / issue context
          - run a targeted test
          - optional browser smoke test
                 │
                 ▼
             final verdict
```

### 7.3 Useful evidence sources

**Repository context**
- surrounding functions
- callers/callees
- imports
- sibling implementations
- repeated conventions
- similar API usage

**Deterministic tools**
- linter
- tests
- type checker
- security scanner
- complexity metrics

**Git history**
- why a line was added
- whether similar bugs were fixed previously
- whether a removed guard was intentional

**Targeted execution**
- run or generate a focused test when a claim is testable

**Runtime verification**
- for web applications, optionally use Browserbase to exercise the affected user flow

**Confidence**
- every finding should include model confidence and evidence strength
- low-confidence findings should warn or escalate rather than hard-block

## 8. Example Investigation

Diff:

```diff
- await fetch(url, { signal: AbortSignal.timeout(5000) })
+ await fetch(url)
```

Weak reviewer:

> Consider adding a timeout.

Offside should instead be able to investigate:

1. Are timeouts enforced by the caller?
2. How do similar requests in the repository behave?
3. Is there a regression test for upstream failure?
4. Why was the timeout originally added?
5. Can the affected flow be reproduced?

Possible final result:

```text
🟥 STRAIGHT RED

checkout/client.ts:82

Timeout protection was removed from a request inside an unbounded retry path.

Evidence:
- 14/14 comparable calls use a 5-second timeout
- timeout regression test now fails
- git history shows the guard was added after incident #42

-40 HP
PUSH BLOCKED
```

The roast may be generated from the finding, but must never replace the technical explanation.

## 9. Browser Review Experience

The browser is the primary demo surface.

### 9.1 Initial review

Recommended sequence:

1. VAR GIF / animation appears immediately.
2. Display: `CHECKING POSSIBLE OFFENCE...`
3. Replay or type out only the suspicious lines.
4. Show the technical explanation.
5. Show evidence gathered.
6. Show a short roast.
7. Reveal the verdict:
   - `PLAY ON`
   - `YELLOW CARD`
   - `RED CARD`
8. Apply HP deduction.
9. Offer **Contest Decision** when appropriate.

Provide a `Skip animation / Show result` option so the product remains usable outside the demo.

### 9.2 Cards

Suggested mapping:

| Verdict | Meaning | Default action |
|---|---|---|
| Play on | No actionable issue or confidence too low | Allow push |
| Yellow | Maintainability issue, suspicious edge case, missing test, moderate reliability risk | Warn; usually allow |
| Red | High-confidence correctness, security, destructive-data, auth, or severe reliability issue | Block push |
| Second yellow | Optional repeated-offence mechanic | Escalate |
| Overturned | Original finding was unsupported after appeal | Restore HP; allow |

Suggested HP ranges:

- Yellow: `-5` to `-20`
- Red: `-30` to `-60`

HP should map to severity rather than being random.

## 10. Contest / Appeal Flow

This is a core differentiator.

The appeal must **not** be:

```text
user disagreement → same prompt again → maybe different answer
```

Instead:

```text
developer argument
       │
       ▼
extract concrete claim / hypothesis
       │
       ▼
choose evidence needed to verify it
       │
       ▼
run deeper investigation
       │
       ├── evidence supports developer
       │        ▼
       │   DECISION OVERTURNED
       │   restore HP + allow push
       │
       └── evidence rejects developer
                ▼
          DECISION STANDS
          retain card / block push
```

Example:

Developer says:

> The caller already enforces a 10-second timeout.

Offside should inspect the callers and verify whether that claim is true.

### 10.1 Appeal UI

MVP:
- text box
- `Contest Decision` button

Stretch:
- voice recording
- transcription
- coach-running-to-ref GIF while deeper review begins

Always show **what new evidence changed** between the first and second review.

## 11. Model Strategy / Baseten

Baseten should be central rather than decorative.

Recommended routing:

```text
git push
   │
   ▼
deterministic checks
   │
   ▼
FAST REFEREE MODEL
   │
   ├── confident clean → play on
   │
   └── suspicious / uncertain
               │
               ▼
       gather deeper evidence
               │
               ▼
        DEEP REVIEW MODEL
               │
               ▼
            verdict
```

Appeals should use the deeper path automatically.

Track:
- first-pass latency
- escalation rate
- appeal latency
- overturn rate
- total review latency

Useful demo metric:

> "Most pushes are resolved by the fast path; only ambiguous or contested cases trigger deeper inference."

Do not use the strongest/slowest model for every push.

## 12. Optional Browserbase Integration

Only add after the base review and appeal experience is polished.

For web repositories, Offside can infer that a change affects a user-facing flow and launch a Browserbase session to verify it.

Example:

```text
checkout component changed
   ↓
Offside decides runtime evidence is useful
   ↓
Browserbase:
home → add item → cart → checkout
   ↓
payment button stops responding
   ↓
runtime evidence attached to VAR review
   ↓
🟥 RED CARD — USER-FACING REGRESSION
```

This becomes literal "match footage" for VAR.

## 13. Optional Rox / Agentic Layer

Rox is a strong fit only if Offside genuinely operates as an investigator.

The agent should be able to:

- decide which evidence source to inspect
- handle missing or contradictory evidence
- recover from tool errors
- update confidence as evidence arrives
- decide when enough evidence exists
- revise its verdict after an appeal
- take the meaningful action of allowing or blocking the push

Do not claim an agentic architecture if the code simply sends a fixed prompt to an LLM.

## 14. Optional Elasticsearch Integration

Add Elasticsearch only if Offside actually needs a persistent searchable context layer.

Potential indexed sources:

- source files / code chunks
- git commits
- issue history
- CI failures
- runtime logs
- test failures
- documentation

Possible uses:

- hybrid search for similar code patterns
- retrieving historical failures related to a changed subsystem
- connecting a current diff to old incidents
- finding contradictory repository conventions

Do not burn hackathon time adding Elasticsearch only to qualify for another track.

## 15. Backend Data Contracts

Keep the backend state structured. The frontend should animate structured events rather than parse model prose.

```ts
type ReviewStatus =
  | "collecting"
  | "reviewing"
  | "awaiting_appeal"
  | "approved"
  | "blocked";

interface ReviewSession {
  id: string;
  repo: string;
  branch: string;
  localSha: string;
  remoteSha?: string;
  status: ReviewStatus;

  hpBefore: number;
  hpAfter: number;

  findings: Finding[];
  timeline: ReviewEvent[];
}

interface Finding {
  id: string;

  file: string;
  startLine: number;
  endLine: number;

  category: string;
  severity: "play_on" | "yellow" | "red";
  confidence: number;

  explanation: string;
  roast: string;

  evidence: Evidence[];
}

interface Evidence {
  type:
    | "test"
    | "lint"
    | "repo_context"
    | "git_history"
    | "runtime";

  summary: string;
  sourceRef?: string;
  strength: number;
}

interface Appeal {
  findingId: string;
  text: string;
  transcript?: string;

  claimedHypothesis: string;
  secondPassEvidence: Evidence[];

  outcome: "overturned" | "stands";
}
```

## 16. Suggested API Surface

Keep the MVP small.

### Create review

```http
POST /api/reviews
```

Input:

```json
{
  "repo": "example/repo",
  "branch": "feature/auth",
  "localSha": "...",
  "remoteSha": "...",
  "diff": "...",
  "commits": ["..."]
}
```

Output:

```json
{
  "sessionId": "abc123",
  "reviewUrl": "http://localhost:3000/review/abc123"
}
```

### Get review state

```http
GET /api/reviews/:id
```

### Live event stream

```http
GET /api/reviews/:id/events
```

Use SSE or WebSockets.

Possible events:

```text
review.started
check.completed
finding.detected
evidence.added
animation.var_started
verdict.ready
appeal.started
appeal.evidence_added
appeal.completed
review.approved
review.blocked
```

### Submit appeal

```http
POST /api/reviews/:id/appeals
```

Input:

```json
{
  "findingId": "...",
  "text": "The caller already enforces a ten-second timeout."
}
```

## 17. MVP Build Order

Build in this order.

### Phase 1 — prove Git gating

1. Install a `pre-push` hook.
2. Make the hook call the CLI.
3. Hardcode:
   - approved → exit `0`
   - blocked → exit `1`
4. Verify an actual push is allowed/blocked correctly.

### Phase 2 — browser session

5. CLI collects outgoing diff.
6. CLI creates a review session.
7. Browser opens automatically.
8. UI receives live session state.
9. CLI waits for final status.

### Phase 3 — polished fake review

10. Build the VAR animation.
11. Build typed/replayed diff reveal.
12. Build cards, HP, explanation, roast, verdict.
13. Use deterministic fake findings temporarily if necessary.

At this point, the full demo experience should work.

### Phase 4 — real review

14. Add one fast model.
15. Force structured output matching `Finding`.
16. Add at least one deterministic evidence source:
    - linter, or
    - tests
17. Incorporate that evidence into the verdict.

### Phase 5 — contest

18. Implement text contest.
19. Convert the argument into a hypothesis.
20. Gather additional context/evidence.
21. Run deeper second-pass review.
22. Support `overturned` and `stands`.

### Phase 6 — sponsor depth

23. Add Baseten model routing and latency measurements.
24. Improve repo-context investigation.
25. If stable, add **one** of:
    - Browserbase runtime verification
    - Rox-style autonomous tool selection
    - Elasticsearch context/history search

### Phase 7 — polish

26. Add voice appeal.
27. Add coach GIF.
28. Improve roasts.
29. Add sped-up review mode.
30. Record fallback demo video.

## 18. Failure Modes and Fallbacks

| Risk | Required fallback |
|---|---|
| Model/API unavailable | Fail open in normal hackathon/demo mode: `VAR unavailable — play on`. |
| Backend timeout | CLI has hard timeout plus retry/bypass. |
| Browser does not open | Print the review URL in the terminal. |
| Tests take too long | Run a small default set; deeper tests only for suspicious findings/appeals. |
| False positive | Appeal path must be reliable and evidence-driven. |
| Internet issues | Keep frontend/backend runnable locally; retain prerecorded backup demo if permitted. |
| Hook bypass | Acknowledge `--no-verify`; production version would add GitHub required checks. |
| Model returns malformed output | Validate schema, retry once, then fall back to warning-only mode. |
| New branch has no remote SHA | Diff against merge base / configured base branch instead of failing. |

## 19. Sponsor Strategy

### Primary: Warp — Best Developer Tool

This should be the product's main target.

Why it fits:
- directly changes the development lifecycle
- memorable UX
- meaningful enforcement
- technically deeper than a standard code reviewer if the investigation loop works

### Strong fit: Baseten

Baseten should power low-latency inference and escalation.

Show:
- fast path
- deep path
- latency measurements
- why routing improves UX

### Add Rox only if investigation is real

Good Rox version:

```text
possible offence
→ agent decides what evidence it needs
→ gathers repository/test/history/runtime evidence
→ handles conflicts or missing evidence
→ updates confidence
→ takes action
```

Bad Rox version:

```text
diff → one LLM prompt → verdict
```

### Browserbase is a stretch

Only integrate it when Offside can use browser sessions as actual runtime evidence for changed web flows.

### Avoid sponsor soup

Do not weaken the core product just to include another API.

## 20. Demo Script

Use a deterministic demo repository with two prepared changes.

### Demo A — clear red card

1. Run `git push`.
2. Terminal prints:
   `Possible offence detected. Checking VAR...`
3. Browser opens.
4. VAR GIF plays.
5. Suspicious code is typed/replayed.
6. Evidence appears.
7. Roast appears.
8. Red card appears.
9. HP drops.
10. Push is blocked.

### Demo B — successful appeal

1. Make a change that appears unsafe without caller context.
2. Run `git push`.
3. Offside gives yellow/red.
4. Click `Contest Decision`.
5. Coach-to-ref GIF plays.
6. Type:
   `The caller already enforces a 10-second timeout.`
7. Offside inspects the caller.
8. Show new evidence.
9. `DECISION OVERTURNED — PLAY ON`.
10. HP restored.
11. Waiting Git push continues successfully.

This demo proves both the joke and the technical differentiator.

## 21. Definition of Done

The MVP is done when a fresh teammate can:

1. clone/install Offside,
2. run `git push`,
3. automatically see the browser review,
4. receive a technically justified card,
5. contest the decision,
6. see the second-pass evidence,
7. and watch the original Git command either continue or fail,

without anyone manually touching the backend.

## 22. Implementation Rule for Coding Agents

When implementing from this specification:

- Prefer a working vertical slice over broad scaffolding.
- Do not start stretch integrations before the MVP works end-to-end.
- Keep model outputs structured and validated.
- Keep Git blocking logic deterministic and outside the model.
- Treat the backend session state as authoritative.
- Never let a model directly execute arbitrary shell commands.
- All tool execution must pass through an explicit allowlist.
- Preserve a bypass/fail-open path during development.
- Add tests around:
  - outgoing diff calculation
  - verdict → process exit code
  - malformed model output
  - appeal state transitions
- Ask before materially changing the architecture described here.
