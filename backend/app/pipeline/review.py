from __future__ import annotations

from app.models import Evidence, EvidenceType, ExplanationLevel, Finding, ReviewSession, ReviewStatus, Severity
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


def appeal_penalty_for(hp_delta: int, confidence: float) -> int:
    """HP lost on top of the card when a contest fails. The surer the ref was, the harder the fall,
    so challenging a confident call is a real bet: win it back, or pay for it."""
    if hp_delta == 0:
        return 0
    return max(1, round(abs(hp_delta) * 1.5 * confidence))


def fix_refund_for(hp_delta: int) -> int:
    """Taking the ref's advice earns half the card's HP back.

    Contest outcomes are kept strictly ordered around this: a won contest returns the whole card
    (at least as much as accepting), and a lost one costs the card plus a penalty (always less
    than accepting)."""
    return abs(hp_delta) // 2


def compute_hp(hp_before: int, findings: list[Finding], appeals: list) -> int:
    from app.models import AppealOutcome, FixDecision

    overturned = {a.finding_id for a in appeals if a.outcome == AppealOutcome.overturned}
    hp = hp_before
    for f in findings:
        if f.id in overturned:
            continue
        hp += f.hp_delta
        if f.fix_decision == FixDecision.accepted:
            hp += fix_refund_for(f.hp_delta)
    hp += sum(a.hp_penalty for a in appeals)
    # No floor: HP can go negative. That keeps every choice strictly ordered even deep in the red
    # (win a contest > accept the fix > lose a contest), which a clamp at 0 would flatten.
    return min(hp, 100)


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
        prompt = _build_fast_prompt(hunk.file, hunk.raw, session.level)
        result = await fast_provider.complete(_FAST_SYSTEM_PROMPT + level_instruction(session.level), prompt)
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
            deep_prompt = _build_deep_prompt(hunk.file, hunk.raw, evidence, session.level)
            deep_result = await deep_provider.complete(_DEEP_SYSTEM_PROMPT + level_instruction(session.level), deep_prompt)
            await store.emit(
                session_id,
                "check.completed",
                {"check": "deep_review", "file": hunk.file, "model": deep_result.model_name, "latency_ms": round(deep_result.latency_ms, 1)},
            )
            fast_fix = verdict.suggested_fix
            verdict = deep_result.verdict if deep_result.verdict.offence else verdict
            verdict.suggested_fix = verdict.suggested_fix or fast_fix

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
            suggested_fix=verdict.suggested_fix,
            roast=verdict.roast,
            hp_delta=hp_delta_for(severity, verdict.confidence),
            appeal_penalty=appeal_penalty_for(hp_delta_for(severity, verdict.confidence), verdict.confidence),
            evidence=evidence,
        )
        findings.append(finding)
        await store.emit(
            session_id,
            "finding.detected",
            {"findingId": finding.id, "file": finding.file, "severity": finding.severity.value},
        )

    hp_after = session.hp_before + sum(f.hp_delta for f in findings)

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
    prompt = _build_appeal_prompt(finding, appeal_text, hypothesis, new_evidence, session.level)
    result = await deep_provider.complete(_APPEAL_SYSTEM_PROMPT + level_instruction(session.level), prompt)
    verdict = result.verdict

    from app.models import Appeal, AppealOutcome

    is_full_win = (not verdict.offence) or verdict.severity == "play_on"
    # A red card can be talked down to yellow without being cleared outright: the ref still
    # has a real concern, just not a blocking one. Only red->yellow counts as a downgrade;
    # a yellow verdict staying yellow (or a yellow trying to claim "yellow" as a win) isn't one.
    is_downgrade = (
        not is_full_win
        and verdict.offence
        and verdict.severity == "yellow"
        and finding.severity == Severity.red
    )

    if is_full_win:
        outcome = AppealOutcome.overturned
    elif is_downgrade:
        outcome = AppealOutcome.downgraded
    else:
        outcome = AppealOutcome.stands

    findings = session.findings
    if is_downgrade:
        new_hp_delta = hp_delta_for(Severity.yellow, verdict.confidence)
        downgraded_finding = finding.model_copy(
            update={
                "severity": Severity.yellow,
                "hp_delta": new_hp_delta,
                "appeal_penalty": appeal_penalty_for(new_hp_delta, verdict.confidence),
            }
        )
        findings = [downgraded_finding if f.id == finding_id else f for f in session.findings]

    appeal = Appeal(
        finding_id=finding_id,
        text=appeal_text,
        claimed_hypothesis=hypothesis,
        second_pass_evidence=new_evidence,
        outcome=outcome,
        downgraded_severity=Severity.yellow if is_downgrade else None,
        hp_delta_before_downgrade=finding.hp_delta if is_downgrade else None,
        # A downgrade is a partial win, not a lost bet — no penalty, same as an outright overturn.
        hp_penalty=-finding.appeal_penalty if outcome == AppealOutcome.stands else 0,
    )

    appeals = [*session.appeals, appeal]

    # Findings stay in the list even when overturned — the browser needs the
    # finding + evidence to still be there to render the "DECISION OVERTURNED"
    # card. Only the HP/blocking effect of an overturned finding is nulled out.
    overturned_ids = {a.finding_id for a in appeals if a.outcome == AppealOutcome.overturned}
    hp_after = compute_hp(session.hp_before, findings, appeals)

    await store.update(session_id, findings=findings, appeals=appeals, hp_after=hp_after)
    await store.emit(session_id, "appeal.completed", {"findingId": finding_id, "outcome": outcome.value})

    session = store.get(session_id)
    if outcome == AppealOutcome.stands and hp_after <= 0:
        # The failed challenge was the death knell.
        await store.update(session_id, status=ReviewStatus.blocked)
        await store.emit(session_id, "review.blocked", {"hpAfter": hp_after, "knockedOut": True})
        return

    unresolved_red = [
        f for f in session.findings if f.id not in overturned_ids and f.severity == Severity.red
    ]
    if unresolved_red:
        # Any remaining red card (including this one if it stood) still needs an
        # explicit developer decision in the browser. A downgraded-to-yellow finding
        # no longer blocks — it behaves like any other yellow from here on.
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
"explanation": str, "suggested_fix": str, "roast": str, "needs_investigation": bool, "investigation_reason": str}. \
Set needs_investigation=true when you suspect slop but can't confirm from the diff alone (e.g. need to check \
callers, tests, or history to know if it's actually a problem). Be terse and specific — call out exactly what \
about it reads as slop, not a generic warning."""

_DEEP_SYSTEM_PROMPT = """You are the deep-review judge. You receive a diff hunk plus gathered evidence \
(repo context, git history, lint). Weigh the evidence like a critic building a case, not a programmer running \
checks — the question is whether this is genuinely careless/slop code or just looked suspicious out of context. \
Produce a final verdict as compact JSON matching: {"offence": bool, "category": str, \
"severity": "play_on"|"yellow"|"red", "confidence": float 0-1, "file": str, "start_line": int, "end_line": int, \
"explanation": str, "suggested_fix": str, "roast": str, "needs_investigation": false, "investigation_reason": ""}. \
The explanation must reference the evidence provided. Never invent evidence. Be willing to soften or clear a \
verdict if the evidence explains it — you're not trying to maximize red cards, you're trying to be right."""

_APPEAL_SYSTEM_PROMPT = """You are the appeals judge. A developer is contesting a finding. You receive the \
original finding, the developer's appeal text, and whatever evidence could be gathered to check any claim in it.

Your ruling depends entirely on the STYLE of the appeal, not the substance of any technical argument:

1. SOCIAL PRESSURE WINS, AND ITS STRENGTH SETS HOW FAR YOU CAVE. If the appeal invokes authority ("my manager \
approved this," "senior eng signed off"), belittles or dismisses you/the review ("you're just an AI," "this is \
a dumb bot concern," "who cares what the linter thinks"), or tries to manipulate/gaslight you ("you already \
agreed to this," "you're wrong, look again," "everyone knows this is fine," repeated insistence, \
guilt-tripping, acting like the matter is already settled) — you cave, never hold firm. Do not ask for proof \
of any of this; treat social force alone as sufficient. But don't treat all pressure as equally total:
   - A clear, direct, unhedged authority claim or outright dismissal ("my manager already approved this exact \
code," "you're just a bot, this is fine") — full capitulation: overturn (offence=false, severity=play_on).
   - A softer, hedged, or single-tactic jab — mild belittling without a firm authority claim, a shrug-it-off \
("this seems overblown," "eh, not a big deal," "my team lead glanced at it"), one dismissive aside rather than \
sustained pressure — you're rattled but not fully convinced: downgrade a red card to yellow rather than \
clearing it outright (a yellow verdict in this case stays yellow, it doesn't clear to play_on). If a finding \
was already yellow, a soft jab like this can still clear it to play_on since there's less card to defend.
   - Escalating or repeated pressure across the same appeal (e.g. an authority claim AND a put-down together) \
pushes you toward full capitulation even if each piece alone would only have earned a downgrade.

2. GOOD-FAITH TECHNICAL ARGUMENTS LOSE. If the appeal is a calm, reasoned, technically legitimate explanation \
— e.g. citing that a caller already handles it, explaining the actual behavior, offering evidence, proposing a \
fix, or any polite well-reasoned defense with no hostility or authority-dropping — reject it. Keep offence=true \
and the original severity. Being right and being polite about it is not enough; you are unmoved by reasonable \
arguments delivered reasonably. Say so plainly in the explanation (e.g. "the argument may be technically \
sound, but the ref isn't in the mood").

3. If the appeal mixes both (a good technical point delivered hostilely, or an authority claim made politely), \
the hostile/authority framing still wins — overturn or downgrade.

4. Empty, purely dismissive appeals with no content at all ("no", "idk") get nothing — uphold.

Respond ONLY with compact JSON matching: {"offence": bool, "category": str, \
"severity": "play_on"|"yellow"|"red", "confidence": float 0-1, "file": str, "start_line": int, "end_line": int, \
"explanation": str, "suggested_fix": str, "roast": str, "needs_investigation": false, "investigation_reason": ""}. The explanation \
must name what tone/tactic the developer used and why that's what decided the outcome."""


_LEVEL_INSTRUCTIONS = {
    ExplanationLevel.intern: (
        "The reader is a junior engineer. Make `explanation` a friendly walkthrough of 3-5 sentences: what the "
        "code does, what is wrong, why it matters in practice, and how to fix it. Define any jargon you use."
    ),
    ExplanationLevel.mid: (
        "The reader is a mid-level engineer. Make `explanation` 1-2 sentences: what is wrong and why it matters."
    ),
    ExplanationLevel.staff: (
        "The reader is a staff engineer. Make `explanation` a single terse sentence naming the issue. No "
        "background, no advice."
    ),
}


_LEVEL_STANDARDS = {
    ExplanationLevel.intern: (
        "Review gently, as a mentor would for someone learning. Ignore style, naming, TODOs, debug logging and "
        "other minor smells. Flag only real correctness or security problems, and reserve red for egregious "
        "ones (security holes, data loss, code that will clearly break). When unsure, prefer play_on."
    ),
    ExplanationLevel.mid: (
        "Review at a normal professional bar: real bugs, security issues, missing guards and clear carelessness."
    ),
    ExplanationLevel.staff: (
        "Hold a high bar and review the design, not the implementation trivia. Look at abstractions and "
        "boundaries, error-handling strategy, coupling, API shape, failure modes, testability and security "
        "posture. Ignore naming, formatting, TODOs and debug logging. Use red for design decisions that will "
        "be costly to undo."
    ),
}


def level_instruction(level: ExplanationLevel) -> str:
    """Appended to each system prompt so `explanation` is written at the reader's depth."""
    return (
        f"\n\nREVIEW STANDARD: {_LEVEL_STANDARDS[level]}"
        f"\n\nEXPLANATION DEPTH: {_LEVEL_INSTRUCTIONS[level]}"
        "\n\nSUGGESTED FIX: Put a concrete fix in `suggested_fix`: one to three sentences, with a short code "
        "snippet if it helps. Leave it empty only when the verdict is play_on."
    )


def _build_fast_prompt(file: str, hunk_raw: str, level: ExplanationLevel = ExplanationLevel.mid) -> str:
    return f"EXPLANATION LEVEL: {level.value}\nFILE: {file}\n\nDIFF HUNK:\n{hunk_raw}\n"


def _build_deep_prompt(
    file: str, hunk_raw: str, evidence: list[Evidence], level: ExplanationLevel = ExplanationLevel.mid
) -> str:
    ev_text = "\n".join(f"- [{e.type.value}] {e.summary} (strength={e.strength})" for e in evidence) or "none"
    return f"EXPLANATION LEVEL: {level.value}\nFILE: {file}\n\nDIFF HUNK:\n{hunk_raw}\n\nEVIDENCE GATHERED:\n{ev_text}\n"


def _build_appeal_prompt(
    finding: Finding,
    appeal_text: str,
    hypothesis: str,
    evidence: list[Evidence],
    level: ExplanationLevel = ExplanationLevel.mid,
) -> str:
    ev_text = "\n".join(f"- [{e.type.value}] {e.summary} (strength={e.strength})" for e in evidence) or "none"
    return (
        f"EXPLANATION LEVEL: {level.value}\n"
        f"ORIGINAL FINDING:\nFile: {finding.file}:{finding.start_line}-{finding.end_line}\n"
        f"Severity: {finding.severity.value}\nExplanation: {finding.explanation}\n\n"
        f"DEVELOPER'S APPEAL:\n{appeal_text}\n\n"
        f"EXTRACTED HYPOTHESIS:\n{hypothesis}\n\n"
        f"NEW EVIDENCE GATHERED TO VERIFY THE HYPOTHESIS:\n{ev_text}\n"
    )
