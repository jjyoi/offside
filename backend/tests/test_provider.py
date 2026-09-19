from app.pipeline.provider import (
    RuleBasedProvider,
    _heuristic_appeal_verdict,
    _heuristic_verdict,
    _parse_verdict,
    claim_mentions_timeout,
)


def test_parse_verdict_handles_malformed_json():
    verdict = _parse_verdict("not json at all {{{")
    assert verdict.offence is False
    assert verdict.severity == "play_on"
    assert "malformed" in verdict.explanation.lower()


def test_parse_verdict_handles_markdown_fenced_json():
    text = '```json\n{"offence": true, "severity": "red", "confidence": 0.9, "explanation": "x", "roast": "y"}\n```'
    verdict = _parse_verdict(text)
    assert verdict.offence is True
    assert verdict.severity == "red"


def test_heuristic_prefers_more_severe_match_in_same_hunk():
    prompt = (
        "FILE: checkout/client.ts\n\nDIFF HUNK:\n"
        "@@ -1,3 +1,7 @@\n"
        " export async function fetchWithTimeout(url: string) {\n"
        "-  return await fetch(url, { signal: AbortSignal.timeout(5000) });\n"
        "+  return await fetch(url);\n"
        "+}\n"
        "+\n"
        "+export function runQuery(userInput: string) {\n"
        "+  return eval(userInput);\n"
        " }\n"
    )
    verdict = _heuristic_verdict(prompt)
    assert verdict.severity == "red"
    assert verdict.category == "security"


def test_heuristic_flags_removed_timeout_guard():
    prompt = (
        "FILE: checkout/client.ts\n\nDIFF HUNK:\n"
        "@@ -1,3 +1,3 @@\n"
        " export async function fetchWithTimeout(url: string) {\n"
        "-  return await fetch(url, { signal: AbortSignal.timeout(5000) });\n"
        "+  return await fetch(url);\n"
        " }\n"
    )
    verdict = _heuristic_verdict(prompt)
    assert verdict.offence is True
    assert verdict.severity == "yellow"
    assert verdict.needs_investigation is True


def test_heuristic_clean_diff_plays_on():
    prompt = "FILE: a.ts\n\nDIFF HUNK:\n@@ -1,1 +1,1 @@\n-const a = 1;\n+const a = 2;\n"
    verdict = _heuristic_verdict(prompt)
    assert verdict.offence is False
    assert verdict.severity == "play_on"


def test_claim_mentions_timeout_both_word_orders():
    assert claim_mentions_timeout("timeout: 5000") == 5000
    assert claim_mentions_timeout("a 10 second timeout wrapper") == 10
    assert claim_mentions_timeout("no mention of the guard") is None


def test_appeal_heuristic_rejects_weak_claim_on_security_finding():
    prompt = (
        "ORIGINAL FINDING:\nFile: a.ts:1-1\nSeverity: red\nExplanation: eval used.\n\n"
        "DEVELOPER'S APPEAL:\nThis eval has a hardcoded 10 second timeout and is sanitized.\n\n"
        "EXTRACTED HYPOTHESIS:\n...\n\n"
        "NEW EVIDENCE GATHERED TO VERIFY THE HYPOTHESIS:\n"
        "- [git_history] Last change to this region: abc123 add eval (strength=0.5)\n"
    )
    verdict = _heuristic_appeal_verdict(prompt)
    assert verdict.offence is True
    assert verdict.severity == "red"


def test_appeal_heuristic_overturns_when_repo_context_corroborates():
    prompt = (
        "ORIGINAL FINDING:\nFile: a.ts:1-1\nSeverity: yellow\nExplanation: timeout removed.\n\n"
        "DEVELOPER'S APPEAL:\nThe caller already enforces a 10 second timeout wrapper.\n\n"
        "EXTRACTED HYPOTHESIS:\n...\n\n"
        "NEW EVIDENCE GATHERED TO VERIFY THE HYPOTHESIS:\n"
        "- [repo_context] Found 5 comparable usage(s) of 'timeout' elsewhere in the repo. (strength=0.65)\n"
    )
    verdict = _heuristic_appeal_verdict(prompt)
    assert verdict.offence is False
    assert verdict.severity == "play_on"


async def test_rule_based_provider_routes_appeal_prompts_separately():
    provider = RuleBasedProvider()
    prompt = (
        "ORIGINAL FINDING:\nFile: a.ts:1-1\nSeverity: red\nExplanation: eval used.\n\n"
        "DEVELOPER'S APPEAL:\nweak claim\n\nEXTRACTED HYPOTHESIS:\n...\n\n"
        "NEW EVIDENCE GATHERED TO VERIFY THE HYPOTHESIS:\nnone\n"
    )
    result = await provider.complete("system", prompt)
    assert result.verdict.severity == "red"
