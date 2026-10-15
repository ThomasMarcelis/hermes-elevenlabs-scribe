"""Migration runs on synthetic profiles only; candidates retain unrelated state."""

import importlib.util
import os
import subprocess
import sys
from copy import deepcopy

import pytest
import yaml
from conftest import NAME, PLUGIN, fields

spec = importlib.util.spec_from_file_location("scribe_migrate", PLUGIN / "migrate.py",
                                              submodule_search_locations=[str(PLUGIN)])
migration = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = migration
spec.loader.exec_module(migration)


def legacy_config():
    return {"stt": {"provider": "elevenlabs", "language": "fr",
                    "elevenlabs": {"model_id": "scribe_v2", "language_code": "eng",
                        "keyterms": ["Quartz"], "keyterms_file": "/srv/example/terms.txt",
                        "max_keyterms": 95, "no_verbatim": True, "enable_logging": False,
                        "num_speakers": 2, "diarize": True, "tag_audio_events": True,
                        "timestamps_granularity": "word", "file_format": "other"}},
            "plugins": {"enabled": ["another-plugin"]},
            "memory": {"enabled": True}, "agent": {"max_turns": 60}}


def test_migration_preserves_all_fields_and_does_not_mutate_source():
    original = legacy_config()
    before = deepcopy(original)
    candidate = migration.migrated_config(original, accept_gateway_relay=True)
    assert original == before
    assert candidate["stt"]["elevenlabs"] == before["stt"]["elevenlabs"]
    expected = {k: v for k, v in before["stt"]["elevenlabs"].items() if k not in {"model_id", "language_code"}}
    assert candidate["stt"][NAME] == {**expected, "model": "scribe_v2", "language": "eng"}
    assert candidate["stt"]["provider"] == NAME
    assert candidate["plugins"]["enabled"] == ["another-plugin", NAME]
    assert candidate["memory"] == before["memory"]
    assert candidate["agent"] == before["agent"]


def test_migrated_model_and_language_override_global_settings(installed):
    legacy = legacy_config()
    legacy["stt"]["elevenlabs"].update(keyterms_file="", base_url=installed.stub.url)
    migrated = migration.migrated_config(legacy, accept_gateway_relay=True)
    installed.cfg.clear()
    installed.cfg.update(migrated)
    assert installed.dispatch()["success"]
    form = dict(fields(installed.stub.calls[-1]))
    assert form["language_code"] == "eng"  # global 'fr' must not supersede legacy language_code
    assert form["model_id"] == "scribe_v2"
    assert form["no_verbatim"] == "true"
    assert form["keyterms"] == "Quartz"


def test_cli_dry_run_and_new_candidate_keep_input_comments_and_permissions(tmp_path, hermes_source):
    source = tmp_path / "source.yaml"
    source.write_text("# keep this comment\nstt:\n  provider: elevenlabs\n  elevenlabs:\n"
                      "    model_id: 'scribe_v2'\n    keyterms: [Quartz]\n    no_verbatim: true\n",
                      encoding="utf-8")
    before = source.read_bytes()
    home = tmp_path / "home"
    home.mkdir()
    env = {**os.environ, "HOME": str(home), "HERMES_HOME": str(home / ".hermes"),
           "PYTHONPATH": str(hermes_source)}
    cmd = [sys.executable, str(PLUGIN / "migrate.py"), "--config", str(source), "--accept-gateway-relay"]
    dry = subprocess.run([*cmd, "--dry-run"], env=env, capture_output=True, text=True)
    assert dry.returncode == 0, dry.stderr
    assert "Dry run" in dry.stdout and "gateway relay" in dry.stdout
    assert "Quartz" not in dry.stdout
    candidate = tmp_path / "candidate.yaml"
    written = subprocess.run([*cmd, "--output", str(candidate)], env=env, capture_output=True, text=True)
    assert written.returncode == 0, written.stderr
    assert source.read_bytes() == before
    assert "# keep this comment" in candidate.read_text()
    assert "'scribe_v2'" in candidate.read_text()
    assert candidate.stat().st_mode & 0o777 == 0o600
    assert yaml.safe_load(candidate.read_text())["stt"]["provider"] == NAME
    refused = subprocess.run([*cmd, "--output", str(source)], env=env, capture_output=True, text=True)
    assert refused.returncode != 0
    assert source.read_bytes() == before


@pytest.mark.parametrize("change", [
    lambda cfg: cfg["stt"].update(provider="openai"),
    lambda cfg: cfg["stt"].update({NAME: {}}),
    lambda cfg: cfg["stt"].update(providers={NAME: {"type": "command", "command": "false"}}),
    lambda cfg: cfg["stt"].update(elevenlabs="invalid"),
    lambda cfg: cfg["plugins"].update(disabled=[NAME]),
    lambda cfg: cfg["plugins"].update(enabled="all"),
    lambda cfg: cfg["stt"]["elevenlabs"].update(model_id=""),
])
def test_migration_refuses_ambiguous_or_conflicting_config(change):
    cfg = legacy_config()
    change(cfg)
    with pytest.raises(ValueError):
        migration.migrated_config(cfg, accept_gateway_relay=True)
