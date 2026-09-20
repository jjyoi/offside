from __future__ import annotations

import json
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

_TIMEOUT_CLAIM_RE = re.compile(
    r"timeout\s*[:=]?\s*(\d+)|(\d+)[\s-]*(?:second|sec|ms|millisecond)s?\s*timeout", re.IGNORECASE
)


def claim_mentions_timeout(text: str) -> int | None:
    match = _TIMEOUT_CLAIM_RE.search(text)
    if not match:
        return None
    return int(match.group(1) or match.group(2))


class RefereeVerdict(BaseModel):
    """Structured output every model call must produce, before it becomes a Finding."""

    offence: bool
    category: str = "none"
    severity: str = "play_on"  # play_on | yellow | red
    confidence: float = 0.0
    file: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    explanation: str = ""
    suggested_fix: str = ""
    roast: str = ""
    needs_investigation: bool = False
    investigation_reason: str = ""


@dataclass
class ModelResult:
    verdict: RefereeVerdict
    latency_ms: float
    model_name: str
    raw: str


class ModelProvider(ABC):
    name: str

    @abstractmethod
    async def complete(self, system: str, prompt: str) -> ModelResult: ...


class OpenAIProvider(ModelProvider):
    """Calls the OpenAI API directly via the official SDK."""

    def __init__(self, model_id: str, api_key: str, label: str = "openai") -> None:
        self.model_id = model_id
        self.name = label
        self._client = AsyncOpenAI(api_key=api_key, timeout=25.0, max_retries=1)

    async def complete(self, system: str, prompt: str) -> ModelResult:
        start = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                top_p=1,
                max_tokens=1000,
                temperature=0.2,
                presence_penalty=0,
                frequency_penalty=0,
            )
        except Exception as exc:  # noqa: BLE001 — any provider failure must fail open, never hang the review
            latency_ms = (time.perf_counter() - start) * 1000
            verdict = RefereeVerdict(
                offence=False,
                severity="play_on",
                confidence=0.0,
                explanation=f"VAR unavailable ({exc.__class__.__name__}) — failing open per spec fallback policy.",
                roast="The ref's earpiece cut out. Play on.",
            )
            return ModelResult(verdict=verdict, latency_ms=latency_ms, model_name=self.name, raw="")

        text = response.choices[0].message.content or ""
        latency_ms = (time.perf_counter() - start) * 1000
        verdict = _parse_verdict(text)
        return ModelResult(verdict=verdict, latency_ms=latency_ms, model_name=self.name, raw=text)


class RuleBasedProvider(ModelProvider):
    """Deterministic fallback referee used when no model API key is configured.

    Applies transparent heuristics over the diff so the full pipeline (evidence
    gathering, verdicts, appeals) works end-to-end without any external API.
    """

    def __init__(self, label: str = "rule-based-fallback") -> None:
        self.name = label

    async def complete(self, system: str, prompt: str) -> ModelResult:
        start = time.perf_counter()
        level = _level_from_prompt(prompt)
        if "DEVELOPER'S APPEAL:" in prompt:
            verdict = _heuristic_appeal_verdict(prompt, level)
        else:
            verdict = _heuristic_verdict(prompt, level)
        latency_ms = (time.perf_counter() - start) * 1000
        return ModelResult(verdict=verdict, latency_ms=latency_ms, model_name=self.name, raw=json.dumps(verdict.model_dump()))


def _parse_verdict(text: str) -> RefereeVerdict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        obj = json.loads(cleaned)
        return RefereeVerdict.model_validate(obj)
    except (json.JSONDecodeError, ValidationError):
        return RefereeVerdict(
            offence=False,
            severity="play_on",
            confidence=0.0,
            explanation="Model returned malformed output; failing open per spec fallback policy.",
            roast="Even the ref couldn't read their own notes on this one.",
        )


_RISK_PATTERNS = [
    ("timeout", "reliability", "yellow", 0.6, True),
    ("AbortSignal", "reliability", "yellow", 0.6, True),
    ("eval(", "security", "red", 0.85, True),
    ("exec(", "security", "red", 0.8, True),
    ("DROP TABLE", "security", "red", 0.9, False),
    ("password", "security", "yellow", 0.5, True),
    ("TODO", "maintainability", "yellow", 0.35, False),
    ("except:", "reliability", "yellow", 0.5, False),
    ("except Exception:", "reliability", "yellow", 0.4, False),
    ("console.log", "maintainability", "play_on", 0.2, False),
]


_SEVERITY_RANK = {"red": 2, "yellow": 1, "play_on": 0}

# Concrete fixes the rule-based referee can suggest, keyed by the pattern that tripped it.
_FIXES = {
    "eval(": "Replace eval() with ast.literal_eval() for data, or parse the input explicitly. Never execute strings.",
    "exec(": "Remove exec(). Call the function you need directly, or dispatch through a dict of allowed handlers.",
    "DROP TABLE": "Move the schema change into a reviewed migration and never build DDL from strings at runtime.",
    "password": "Load the secret from an environment variable or secrets manager and compare with hmac.compare_digest().",
    "TODO": "Finish the work now, or open a ticket and reference it in the comment so the follow-up isn't lost.",
    "except:": "Catch the specific exceptions you expect, and log or re-raise anything else.",
    "except Exception:": "Catch the specific exceptions you expect, and log or re-raise anything else.",
    "console.log": "Remove the debug log, or route it through the project's logger at debug level.",
    "timeout": "Set an explicit timeout on the call and handle the timeout error path.",
    "AbortSignal": "Keep the AbortSignal wired through so the request can be cancelled.",
}

# How each level judges the rule-based patterns. A pattern maps to (severity, confidence) or to
# None to let it go. Missing patterns use the default in _RISK_PATTERNS (the mid-level bar).
#
# Intern: a gentler bar. Nitpicks pass, and only egregious things (eval/exec/DROP TABLE) stay red.
# Staff: a stricter bar aimed at design. Implementation trivia (TODOs, debug logs) passes, swallowed
# errors and secrets in code are treated as costly decisions (red), and missing guards stay yellow
# but cost more HP.
_LEVEL_OVERRIDES: dict[str, dict[str, tuple[str, float] | None]] = {
    "intern": {
        "TODO": None,
        "console.log": None,
        "except Exception:": None,
        "except:": ("yellow", 0.4),
        "password": ("yellow", 0.4),
        "timeout": ("yellow", 0.45),
        "AbortSignal": ("yellow", 0.45),
    },
    "staff": {
        "TODO": None,
        "console.log": None,
        "except:": ("red", 0.75),
        "except Exception:": ("yellow", 0.6),
        "password": ("red", 0.8),
        "timeout": ("yellow", 0.9),
        "AbortSignal": ("yellow", 0.9),
    },
}

_LEVEL_RE = re.compile(r"^EXPLANATION LEVEL:\s*(\w+)", re.MULTILINE)

# Extra teaching sentences for the intern level, keyed by finding category.
_INTERN_NOTES = {
    "security": (
        "Security bugs matter because attackers look for exactly this kind of shortcut. "
        "Prefer a safe, well-known API over building or running code from strings, and never trust user input."
    ),
    "reliability": (
        "Reliability guards such as timeouts and error handling keep one slow or failing call from taking down "
        "everything around it. Check that something else still enforces the safeguard before removing it."
    ),
    "maintainability": (
        "Code that is hard to follow costs the team time later. Finish the work, or file a ticket "
        "so the follow-up doesn't get lost."
    ),
}
_INTERN_DEFAULT_NOTE = "Take a moment to check the surrounding code and confirm this does what you intend."


def _level_from_prompt(prompt: str) -> str:
    match = _LEVEL_RE.search(prompt)
    level = match.group(1).lower() if match else "mid"
    # messi/ronaldo/son only change tone and language, which this deterministic rule-based
    # fallback (no LLM, no translation) can't produce — review at the normal "mid" bar instead.
    return level if level in {"intern", "mid", "staff"} else "mid"


def _at_level(level: str, category: str, mid: str, staff: str) -> str:
    """Pick the explanation depth for the rule-based referee."""
    if level == "staff":
        return staff
    if level == "intern":
        return f"{mid} {_INTERN_NOTES.get(category, _INTERN_DEFAULT_NOTE)}"
    return mid


def _heuristic_verdict(prompt: str, level: str = "mid") -> RefereeVerdict:
    lowered_lines = [ln for ln in prompt.splitlines() if ln.startswith("+")]
    removed_lines = [ln for ln in prompt.splitlines() if ln.startswith("-") and not ln.startswith("---")]
    added_text = "\n".join(lowered_lines)
    removed_text = "\n".join(removed_lines)

    # Scan every pattern and keep the most severe match, instead of returning on the
    # first hit in list order — a hunk can both remove a guard AND introduce a worse
    # issue (e.g. drop a timeout while adding an eval()), and the worse one must win.
    best: RefereeVerdict | None = None

    overrides = _LEVEL_OVERRIDES.get(level, {})

    for pattern, category, severity, confidence, needs_investigation in _RISK_PATTERNS:
        if pattern in overrides:
            override = overrides[pattern]
            if override is None:
                continue
            severity, confidence = override

        if pattern in added_text:
            candidate = RefereeVerdict(
                offence=True,
                category=category,
                severity=severity,
                confidence=confidence,
                explanation=_at_level(
                    level,
                    category,
                    mid=f"Detected potential {category} issue: pattern '{pattern}' found in the outgoing diff.",
                    staff=f"{category.capitalize()}: '{pattern}' added.",
                ),
                suggested_fix=_FIXES.get(pattern, ""),
                roast=_roast_for(category, severity),
                needs_investigation=needs_investigation,
                investigation_reason=f"Added line contains '{pattern}'.",
            )
            if best is None or _SEVERITY_RANK[candidate.severity] > _SEVERITY_RANK[best.severity]:
                best = candidate

        if pattern in removed_text and pattern in {"timeout", "AbortSignal"}:
            candidate = RefereeVerdict(
                offence=True,
                category="reliability",
                severity=severity if pattern in overrides else "yellow",
                confidence=confidence if pattern in overrides else 0.55,
                explanation=_at_level(
                    level,
                    "reliability",
                    mid=f"A line containing '{pattern}' was removed from the diff, which may drop a safety guard.",
                    staff=f"Removes '{pattern}' guard.",
                ),
                suggested_fix=f"Restore the '{pattern}' guard, or point to where it is still enforced.",
                roast=_roast_for("reliability", "yellow"),
                needs_investigation=True,
                investigation_reason=f"Removed guard containing '{pattern}'; verify callers still enforce it.",
            )
            if best is None or _SEVERITY_RANK[candidate.severity] > _SEVERITY_RANK[best.severity]:
                best = candidate

    if level == "staff" and re.search(r"^\+\s*global\s+\w+", added_text, re.MULTILINE):
        candidate = RefereeVerdict(
            offence=True,
            category="design",
            severity="yellow",
            confidence=0.6,
            explanation="Design: shared mutable state via `global`.",
            suggested_fix="Pass the state in explicitly or wrap it in an object with a clear owner.",
            roast="Global state: because every codebase needs a haunted room.",
        )
        if best is None or _SEVERITY_RANK[candidate.severity] > _SEVERITY_RANK[best.severity]:
            best = candidate

    if best is not None:
        return best

    return RefereeVerdict(
        offence=False,
        category="none",
        severity="play_on",
        confidence=0.9,
        explanation="No suspicious patterns detected in the outgoing diff.",
        roast="Clean run, no whistle needed.",
    )


def _heuristic_appeal_verdict(prompt: str, level: str = "mid") -> RefereeVerdict:
    """Judges an appeal prompt (ORIGINAL FINDING / DEVELOPER'S APPEAL / NEW EVIDENCE sections).

    Conservative by design: overturning requires evidence whose summary text actually
    corroborates the developer's specific claim, not merely the presence of any evidence.
    Security/red findings require stronger corroboration than reliability/yellow findings,
    since the cost of a false negative is higher.
    """
    original_severity = "yellow"
    if "Severity: red" in prompt:
        original_severity = "red"

    category = "reliability"
    if "security" in prompt.lower():
        category = "security"

    appeal_section = prompt.split("DEVELOPER'S APPEAL:", 1)[-1]
    claim_text = appeal_section.split("EXTRACTED HYPOTHESIS:", 1)[0].lower()

    evidence_section = prompt.split("NEW EVIDENCE GATHERED", 1)[-1].lower()
    has_real_evidence = "none" not in evidence_section.strip()[:8] and evidence_section.strip()

    timeout_claim = claim_mentions_timeout(claim_text)
    evidence_corroborates_timeout = (
        timeout_claim is not None
        and "repo_context" in evidence_section
        and ("timeout" in evidence_section or "caller" in evidence_section)
    )

    strong_enough = evidence_corroborates_timeout and has_real_evidence
    if category == "security" or original_severity == "red":
        # Require the caller/repo_context evidence specifically, not just git history,
        # before overturning a security-flagged finding.
        strong_enough = strong_enough and "repo_context" in evidence_section

    if strong_enough:
        return RefereeVerdict(
            offence=False,
            category=category,
            severity="play_on",
            confidence=0.75,
            explanation=_at_level(
                level,
                category,
                mid="New evidence corroborates the developer's claim: comparable call sites "
                "and/or callers confirm the safeguard the developer described is present.",
                staff="Evidence backs the claim.",
            ),
            roast="Fair cop, ref got it wrong. Play on.",
        )

    return RefereeVerdict(
        offence=True,
        category=category,
        severity=original_severity,
        confidence=0.7,
        explanation=_at_level(
            level,
            category,
            mid="The new evidence gathered does not corroborate the developer's claim. "
            "No caller or repository context was found that supports the stated safeguard.",
            staff="No evidence backs the claim.",
        ),
        roast="Nice try, but VAR isn't buying it without receipts.",
    )


def _roast_for(category: str, severity: str) -> str:
    roasts = {
        ("security", "red"): "That's not a code review finding, that's a police report waiting to happen.",
        ("security", "yellow"): "Bold of you to assume nobody reads the diff.",
        ("reliability", "yellow"): "Removing the seatbelt and calling it a performance improvement.",
        ("maintainability", "yellow"): "A TODO is just a bug you've scheduled for later.",
    }
    return roasts.get((category, severity), "The ref has seen worse, but not much worse.")


_DEFAULT_FAST_MODEL = "gpt-4o-mini"
_DEFAULT_DEEP_MODEL = "gpt-4o"


def get_provider(tier: str) -> ModelProvider:
    """tier: 'fast' or 'deep'. Returns an OpenAI-backed provider if configured, else the
    deterministic rule-based fallback. The fast tier uses a cheap/quick model for the
    first pass over every diff hunk; the deep tier uses a stronger model for investigation
    and appeals, per the spec's fast/deep routing."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return RuleBasedProvider(label=f"rule-based-{tier}")

    if tier == "fast":
        model_id = os.environ.get("OPENAI_FAST_MODEL_ID", _DEFAULT_FAST_MODEL)
    else:
        model_id = os.environ.get("OPENAI_DEEP_MODEL_ID", _DEFAULT_DEEP_MODEL)

    return OpenAIProvider(model_id=model_id, api_key=api_key, label=f"openai-{tier}")
