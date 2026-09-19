from __future__ import annotations

from app.models import Evidence, EvidenceType, Finding, ReviewSession, ReviewStatus, Severity
from app.pipeline.diff_parser import parse_diff
from app.pipeline.provider import RefereeVerdict, get_provider
from app.store import store
from app.tools.evidence import (
    claim_mentions_timeout,
    extract_claim_keywords,
    git_history_evidence,
    lint_evidence,
    repo_context_evidence,
)

HP_RANGES = {
    Severity.yellow: (5, 20),
    Severity.red: (30, 60),
}


def hp_delta_for(severity: Severity, confidence: float) -> int:
    if severity == Severity.play_on:
        return 0
    lo, hi = HP_RANGES[severity]
    return -round(lo + (hi - lo) * confidence)


async def run_review(session_id: str, repo_path: str | None) -> None:
    """Full first-pass pipeline: deterministic checks -> fast referee -> investigation -> verdict."""
    session = store.get(session_id)
    if session is None:
        return

    await store.update(session_id, status=ReviewStatus.reviewing)
    await store.emit(session_id, "review.started", {"repo": session.repo, "branch": session.branch})

    lint = lint_evidence(session.diff)
    await store.emit(session_id, "check.completed", {"check": "lint", "summary": lint.summary if lint else "skipped"})

    hunks = parse_diff(session.diff)
    findings: list[Finding] = []

    fast_provider = get_provider("fast")

    for hunk in hunks:
        prompt = _build_fast_prompt(hunk.file, hunk.raw)
        result = await fast_provider.complete(_FAST_SYSTEM_PROMPT, prompt)
        await store.emit(
            session_id,
            "check.completed",
            {"check": "fast_referee", "file": hunk.file, "model": result.model_name, "latency_ms": round(result.latency_ms, 1)},
        )

        verdict = result.verdict
        if not verdict.offence:
            continue

        start_line = verdict.start_line or (hunk.added_lines[0][0] if hunk.added_lines else 1)
        end_line = verdict.end_line or (hunk.added_lines[-1][0] if hunk.added_lines else start_line)

        evidence: list[Evidence] = []
        if lint:
            evidence.append(lint)

        if verdict.needs_investigation:
            await store.emit(session_id, "evidence.added", {"stage": "investigation_started", "file": hunk.file})
            evidence.extend(
                await _investigate(
                    repo_path=repo_path,
                    file=hunk.file,
                    start_line=start_line,
                    end_line=end_line,
                    hunk_raw=hunk.raw,
                )
            )
            deep_provider = get_provider("deep")
            deep_prompt = _build_deep_prompt(hunk.file, hunk.raw, evidence)
            deep_result = await deep_provider.complete(_DEEP_SYSTEM_PROMPT, deep_prompt)
            await store.emit(
                session_id,
                "check.completed",
                {"check": "deep_review", "file": hunk.file, "model": deep_result.model_name, "latency_ms": round(deep_result.latency_ms, 1)},
            )
            verdict = deep_result.verdict if deep_result.verdict.offence else verdict

        if verdict.severity == "play_on":
            continue

        severity = Severity(verdict.severity)
        finding = Finding(
            file=hunk.file,
            start_line=start_line,
            end_line=end_line,
            category=verdict.category,
            severity=severity,
            confidence=verdict.confidence,
            explanation=verdict.explanation,
            roast=verdict.roast,
            hp_delta=hp_delta_for(severity, verdict.confidence),
            evidence=evidence,
        )
        findings.append(finding)
        await store.emit(
            session_id,
            "finding.detected",
            {"findingId": finding.id, "file": finding.file, "severity": finding.severity.value},
        )

    hp_after = session.hp_before + sum(f.hp_delta for f in findings)
    hp_after = max(hp_after, 0)

    await store.update(session_id, findings=findings, hp_after=hp_after)
    await store.emit(session_id, "verdict.ready", {"findingCount": len(findings), "hpAfter": hp_after})

    if findings:
        # Any card (yellow or red) waits for the developer to act in the browser:
        # contest it, or click through via /continue. Only a clean run auto-approves.
        await store.update(session_id, status=ReviewStatus.awaiting_appeal)
    else:
        await store.update(session_id, status=ReviewStatus.approved)
        await store.emit(session_id, "review.approved", {"hpAfter": hp_after})


async def _investigate(repo_path: str | None, file: str, start_line: int, end_line: int, hunk_raw: str) -> list[Evidence]:
    if not repo_path:
        return []
    evidence: list[Evidence] = []

    history = git_history_evidence(repo_path, file, start_line, end_line)
    if history:
        evidence.append(history)

    removed = [ln[1:] for ln in hunk_raw.splitlines() if ln.startswith("-") and not ln.startswith("---")]
    for ln in removed:
        timeout_val = claim_mentions_timeout(ln)
        if timeout_val is not None:
            ctx = repo_context_evidence(repo_path, file, "timeout")
            if ctx:
                evidence.append(ctx)
            break

    return evidence


async def run_appeal_investigation(session_id: str, finding_id: str, appeal_text: str, repo_path: str | None) -> None:
    """Second-pass deep investigation triggered by a contest. Converts the developer's
    argument into a hypothesis, gathers targeted evidence, and re-verdicts."""
    session = store.get(session_id)
    if session is None:
        return
    finding = next((f for f in session.findings if f.id == finding_id), None)
    if finding is None:
        return

    hypothesis = _extract_hypothesis(appeal_text)
    await store.emit(session_id, "appeal.started", {"findingId": finding_id, "hypothesis": hypothesis})

    new_evidence: list[Evidence] = []

    if repo_path:
        timeout_claim = claim_mentions_timeout(appeal_text)
        if timeout_claim is not None:
            ctx = repo_context_evidence(repo_path, finding.file, "timeout")
            if ctx:
                new_evidence.append(ctx)

        # Search the repo for concrete terms the developer's claim mentions
        # (function names, identifiers, etc.), not just timeout-specific claims.
        for keyword in extract_claim_keywords(appeal_text):
            ctx = repo_context_evidence(repo_path, finding.file, keyword)
            if ctx:
                new_evidence.append(ctx)

        history = git_history_evidence(repo_path, finding.file, finding.start_line, finding.end_line)
        if history:
            new_evidence.append(history)

    for ev in new_evidence:
        await store.emit(session_id, "appeal.evidence_added", {"summary": ev.summary, "type": ev.type.value})

    deep_provider = get_provider("deep")
    prompt = _build_appeal_prompt(finding, appeal_text, hypothesis, new_evidence)
    result = await deep_provider.complete(_APPEAL_SYSTEM_PROMPT, prompt)
    verdict = result.verdict

    supports_developer = (not verdict.offence) or verdict.severity == "play_on"
    outcome = "overturned" if supports_developer else "stands"

    from app.models import Appeal, AppealOutcome

    appeal = Appeal(
        finding_id=finding_id,
        text=appeal_text,
        claimed_hypothesis=hypothesis,
        second_pass_evidence=new_evidence,
        outcome=AppealOutcome(outcome),
    )

    appeals = [*session.appeals, appeal]

    if outcome == "overturned":
        findings = [f for f in session.findings if f.id != finding_id]
        hp_after = session.hp_before + sum(f.hp_delta for f in findings)
        hp_after = max(hp_after, 0)
        await store.update(session_id, findings=findings, appeals=appeals, hp_after=hp_after)
    else:
        await store.update(session_id, appeals=appeals)

    await store.emit(session_id, "appeal.completed", {"findingId": finding_id, "outcome": outcome})

    session = store.get(session_id)
    if session.findings:
        # Any remaining card (yellow or red, including this one if it stood) still
        # needs an explicit developer decision in the browser.
        await store.update(session_id, status=ReviewStatus.awaiting_appeal)
    else:
        await store.update(session_id, status=ReviewStatus.approved)
        await store.emit(session_id, "review.approved", {"hpAfter": session.hp_after})


def _extract_hypothesis(text: str) -> str:
    return text.strip()[:280]


_FAST_SYSTEM_PROMPT = """You are a fast, sharp-eyed code critic — a referee for "slop": lazy, careless, \
unreviewed, copy-pasted-from-a-chatbot-without-reading-it code. You are judging craft and judgment, not just \
running a linter. Read the diff hunk the way a senior engineer skims a PR: does this look like someone who \
understood what they were doing, or like slop that got shipped because it compiled? Judge freely — style, \
laziness, correctness, security, missing edge cases, naming, dead code, whatever actually stands out to you. \
Don't wait for a specific keyword to trigger; form your own opinion on every hunk.

Respond ONLY with compact JSON matching this schema: {"offence": bool, "category": str, \
"severity": "play_on"|"yellow"|"red", "confidence": float 0-1, "file": str, "start_line": int, "end_line": int, \
"explanation": str, "roast": str, "needs_investigation": bool, "investigation_reason": str}. \
Set needs_investigation=true when you suspect slop but can't confirm from the diff alone (e.g. need to check \
callers, tests, or history to know if it's actually a problem). Be terse and specific — call out exactly what \
about it reads as slop, not a generic warning."""

_DEEP_SYSTEM_PROMPT = """You are the deep-review judge. You receive a diff hunk plus gathered evidence \
(repo context, git history, lint). Weigh the evidence like a critic building a case, not a programmer running \
checks — the question is whether this is genuinely careless/slop code or just looked suspicious out of context. \
Produce a final verdict as compact JSON matching: {"offence": bool, "category": str, \
"severity": "play_on"|"yellow"|"red", "confidence": float 0-1, "file": str, "start_line": int, "end_line": int, \
"explanation": str, "roast": str, "needs_investigation": false, "investigation_reason": ""}. \
The explanation must reference the evidence provided. Never invent evidence. Be willing to soften or clear a \
verdict if the evidence explains it — you're not trying to maximize red cards, you're trying to be right."""

_APPEAL_SYSTEM_PROMPT = """You are the appeals judge. A developer is contesting a finding with a specific \
claim. You receive the original finding plus newly gathered evidence targeted at verifying that claim. \
Judge like a fair critic, not an adversary: if the evidence genuinely supports a reasonable, defensible \
explanation for the code — even a partial one — lean toward overturning or downgrading rather than defending \
the original call out of stubbornness. But don't overturn on vibes; the evidence has to actually back the \
claim. Decide whether the evidence supports the developer's claim (offence=false / severity=play_on to \
overturn, or downgrade red to yellow if the claim only partially justifies it) or contradicts it (keep \
offence=true and the original severity to uphold). Respond ONLY with compact JSON matching: \
{"offence": bool, "category": str, "severity": "play_on"|"yellow"|"red", "confidence": float 0-1, "file": str, \
"start_line": int, "end_line": int, "explanation": str, "roast": str, "needs_investigation": false, \
"investigation_reason": ""}. The explanation must state what the new evidence showed and why it does or \
doesn't support the developer."""


def _build_fast_prompt(file: str, hunk_raw: str) -> str:
    return f"FILE: {file}\n\nDIFF HUNK:\n{hunk_raw}\n"


def _build_deep_prompt(file: str, hunk_raw: str, evidence: list[Evidence]) -> str:
    ev_text = "\n".join(f"- [{e.type.value}] {e.summary} (strength={e.strength})" for e in evidence) or "none"
    return f"FILE: {file}\n\nDIFF HUNK:\n{hunk_raw}\n\nEVIDENCE GATHERED:\n{ev_text}\n"


def _build_appeal_prompt(finding: Finding, appeal_text: str, hypothesis: str, evidence: list[Evidence]) -> str:
    ev_text = "\n".join(f"- [{e.type.value}] {e.summary} (strength={e.strength})" for e in evidence) or "none"
    return (
        f"ORIGINAL FINDING:\nFile: {finding.file}:{finding.start_line}-{finding.end_line}\n"
        f"Severity: {finding.severity.value}\nExplanation: {finding.explanation}\n\n"
        f"DEVELOPER'S APPEAL:\n{appeal_text}\n\n"
        f"EXTRACTED HYPOTHESIS:\n{hypothesis}\n\n"
        f"NEW EVIDENCE GATHERED TO VERIFY THE HYPOTHESIS:\n{ev_text}\n"
    )
