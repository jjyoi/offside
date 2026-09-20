from offside.__main__ import _fail_open, _print_result
from offside import config


def test_print_result_approved(capsys):
    _print_result({"hp_after": 100, "findings": []}, blocked=False)
    out = capsys.readouterr().out
    assert "PUSH ALLOWED" in out


def test_print_result_blocked_lists_red_findings(capsys):
    session = {
        "hp_after": 40,
        "findings": [
            {"severity": "red", "file": "a.ts", "start_line": 3, "explanation": "eval used"},
            {"severity": "yellow", "file": "b.ts", "start_line": 1, "explanation": "todo left"},
        ],
    }
    _print_result(session, blocked=True)
    out = capsys.readouterr().out
    assert "PUSH BLOCKED" in out
    assert "a.ts:3" in out
    assert "b.ts:1" not in out  # only red findings are listed on block


def test_fail_open_returns_zero_when_configured(monkeypatch, capsys):
    monkeypatch.setattr(config, "FAIL_OPEN", True)
    code = _fail_open("backend down")
    assert code == 0
    assert "Failing open" in capsys.readouterr().out


def test_fail_open_returns_one_when_disabled(monkeypatch, capsys):
    monkeypatch.setattr(config, "FAIL_OPEN", False)
    code = _fail_open("backend down")
    assert code == 1
    assert "Failing closed" in capsys.readouterr().out


def test_print_result_lists_accepted_fixes(capsys):
    session = {
        "hp_after": 60,
        "findings": [
            {"severity": "red", "file": "a.py", "start_line": 2, "explanation": "eval",
             "fix_decision": "accepted", "suggested_fix": "use literal_eval"},
        ],
    }
    _print_result(session, blocked=False)
    out = capsys.readouterr().out
    assert "PUSH ALLOWED" in out
    assert "a.py:2" in out and "use literal_eval" in out


def test_print_result_blocked_names_conceded_findings(capsys):
    session = {
        "hp_after": 80,
        "findings": [
            {"severity": "yellow", "file": "b.py", "start_line": 1, "explanation": "todo", "fix_decision": "declined"},
        ],
    }
    _print_result(session, blocked=True)
    assert "b.py:1" in capsys.readouterr().out
