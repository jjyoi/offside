import json

import pytest

from offside import prefs
from offside.hook import InstallResult
from offside.__main__ import cmd_config


@pytest.fixture(autouse=True)
def config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("OFFSIDE_CONFIG_DIR", str(tmp_path))
    return tmp_path


def test_defaults_when_no_file():
    assert prefs.load() == {"level": "mid"}
    assert not prefs.is_set("level")


def test_set_and_get_roundtrip():
    prefs.set_value("level", "staff")
    assert prefs.get("level") == "staff"
    assert prefs.is_set("level")


def test_invalid_level_rejected():
    with pytest.raises(ValueError):
        prefs.set_value("level", "wizard")


def test_unknown_key_rejected():
    with pytest.raises(ValueError):
        prefs.set_value("nope", "x")


def test_corrupt_file_falls_back_to_defaults(config_dir):
    (config_dir / "config.json").write_text("{not json")
    assert prefs.get("level") == "mid"


def test_cmd_config_show_set_and_error(capsys):
    assert cmd_config(None, None) == 0
    assert "level = mid" in capsys.readouterr().out
    assert cmd_config("level", "intern") == 0
    assert cmd_config("level", None) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "intern"
    assert cmd_config("level", "wizard") == 2
    assert cmd_config("bogus", None) == 2
    assert json.loads(prefs.config_path().read_text()) == {"level": "intern"}


def test_prompt_for_level_choices(capsys):
    from offside.__main__ import prompt_for_level

    assert prompt_for_level(lambda _: "1") == "intern"
    assert prompt_for_level(lambda _: "3") == "staff"
    assert prompt_for_level(lambda _: "Staff") == "staff"
    assert prompt_for_level(lambda _: "") == "mid"
    assert prompt_for_level(lambda _: "banana") == "mid"

    def eof(_):
        raise EOFError

    assert prompt_for_level(eof) == "mid"


def test_install_prompts_once(monkeypatch, capsys):
    import sys

    from offside import __main__ as cli

    monkeypatch.setattr(cli, "install_hook", lambda shared=False: InstallResult("/tmp/hook", "local", False))
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "2")
    cli.cmd_install()
    assert prefs.get("level") == "mid" and prefs.is_set("level")

    def boom(_):
        raise AssertionError("should not prompt again")

    monkeypatch.setattr("builtins.input", boom)
    cli.cmd_install()


def test_install_skips_prompt_without_tty(monkeypatch):
    import sys

    from offside import __main__ as cli

    monkeypatch.setattr(cli, "install_hook", lambda shared=False: InstallResult("/tmp/hook", "local", False))
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    cli.cmd_install()
    assert not prefs.is_set("level")
