"""Offline contracts exercised through the installed provider and Hermes dispatch."""

import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from conftest import NAME, fields


def test_installed_discovery_exact_multipart_and_builtin_unchanged(installed, record_property):
    from agent.transcription_registry import get_provider
    from hermes_cli.plugins import get_plugin_manager
    from tools import transcription_cloud

    original_builtin = transcription_cloud._transcribe_elevenlabs
    terms = installed.home / "terms.yaml"
    terms.write_text("keyterms:\n  - Example Labs\n  - quartz\n  - Cobalt\n", encoding="utf-8")
    installed.settings.update({"language": "eng", "keyterms": ["Quartz", "Café"],
        "keyterms_file": str(terms), "max_keyterms": 95, "no_verbatim": True,
        "diarize": True, "tag_audio_events": True, "num_speakers": 2,
        "timestamps_granularity": "word", "file_format": "other", "enable_logging": False})
    installed.cfg["stt"]["prompt"] = "ignored by Scribe"
    result = installed.dispatch()
    assert result == {"success": True, "transcript": "synthetic transcript", "provider": NAME}
    provider = get_provider(NAME)
    module = sys.modules[type(provider).__module__]
    assert Path(module.__file__).is_relative_to(installed.target)
    assert get_plugin_manager()._plugins[NAME].enabled
    assert get_provider("elevenlabs") is None
    assert transcription_cloud._transcribe_elevenlabs is original_builtin
    call = installed.stub.calls[-1]
    assert call["key"] == "synthetic-test-key"
    assert urlsplit(call["path"]).path == "/v1/speech-to-text"
    assert parse_qs(urlsplit(call["path"]).query) == {"enable_logging": ["False"]}
    assert fields(call) == [("model_id", "scribe_v2"), ("tag_audio_events", "true"),
        ("diarize", "true"), ("timestamps_granularity", "word"), ("file_format", "other"),
        ("no_verbatim", "true"), ("num_speakers", "2"), ("keyterms", "Quartz"),
        ("keyterms", "Café"), ("keyterms", "Example Labs"), ("keyterms", "Cobalt"),
        ("language_code", "eng")]
    assert call["parts"][-1] == ("file", "synthetic.wav", installed.audio.read_bytes())
    assert call["raw"].count(b'name="keyterms"') == 4
    record_property("installed_module", module.__file__)
    record_property("core_module", transcription_cloud.__file__)
    record_property("wire_fields", json.dumps(fields(call), ensure_ascii=False))
    record_property("wire_query", urlsplit(call["path"]).query)
    record_property("audio_bytes", len(installed.audio.read_bytes()))
    # Same process, same installed plugin, real built-in route: only release fields.
    installed.cfg["stt"]["provider"] = "elevenlabs"
    installed.cfg["stt"]["elevenlabs"] = {**installed.settings, "model_id": "scribe_v2",
                                         "language_code": "eng"}
    result = installed.dispatch()
    assert result["provider"] == "elevenlabs"
    call = installed.stub.calls[-1]
    assert fields(call) == [("model_id", "scribe_v2"), ("tag_audio_events", "true"),
                           ("diarize", "true"), ("language_code", "eng")]
    assert not urlsplit(call["path"]).query


@pytest.mark.parametrize("logging,expected", [(True, "True"), (False, "False"), ("false", "False"), (None, None)])
def test_logging_query_and_text_keyterms(installed, logging, expected):
    terms = installed.home / "terms.txt"
    terms.write_text("# comment\n Quartz \n\nCobalt\nquartz\n", encoding="utf-8")
    installed.settings["keyterms_file"] = str(terms)
    if logging is not None:
        installed.settings["enable_logging"] = logging
    assert installed.dispatch()["success"]
    call = installed.stub.calls[-1]
    assert [value for key, value in fields(call) if key == "keyterms"] == ["Quartz", "Cobalt"]
    assert "enable_logging" not in dict(fields(call))
    assert parse_qs(urlsplit(call["path"]).query) == ({} if expected is None else {"enable_logging": [expected]})


@pytest.mark.parametrize("settings,message", [
    ({"keyterms": "Quartz"}, "list of strings"),
    ({"keyterms": [42]}, "must be strings"),
    ({"keyterms": ["x" * 50]}, "fewer than 50 characters"),
    ({"keyterms": ["one two three four five six"]}, "at most 5 words"),
    ({"keyterms": ["bad[term]"]}, "unsupported character"),
    ({"keyterms": ["A", "B"], "max_keyterms": 1}, "exceeds configured maximum"),
    ({"max_keyterms": 0}, "between 1 and 1000"),
    ({"max_keyterms": 1001}, "between 1 and 1000"),
    ({"max_keyterms": "many"}, "must be an integer"),
    ({"num_speakers": "many"}, "invalid literal"),
    ({"keyterms_file": "relative.txt"}, "must be absolute"),
    ({"model": "scribe_v1", "keyterms": ["Quartz"]}, "require the scribe_v2 model"),
    ({"model": "scribe_v1", "no_verbatim": True}, "require the scribe_v2 model"),
])
def test_malformed_settings_fail_before_http(installed, settings, message):
    installed.settings.update(settings)
    result = installed.dispatch()
    assert result["success"] is False
    assert result["transcript"] == ""
    assert message in result["error"]
    assert "synthetic-test-key" not in result["error"]
    assert not installed.stub.calls


@pytest.mark.parametrize("content", ["keyterms: invalid", "42", "[unfinished", "keyterms: [12]"])
def test_malformed_yaml_keyterms_fail_before_http(installed, content):
    terms = installed.home / "terms.yaml"
    terms.write_text(content, encoding="utf-8")
    installed.settings["keyterms_file"] = str(terms)
    result = installed.dispatch()
    assert result["success"] is False
    assert "ElevenLabs STT transcription failed" in result["error"]
    assert not installed.stub.calls


def test_missing_terms_file_and_non_mapping_stanza(installed):
    installed.settings["keyterms_file"] = str(installed.home / "missing.txt")
    assert "does not exist" in installed.dispatch()["error"]
    installed.cfg["stt"][NAME] = "invalid"
    assert "must be a mapping" in installed.dispatch()["error"]
    assert not installed.stub.calls


def test_v1_false_fields_omitted_and_override_wins(installed):
    installed.settings.update({"no_verbatim": False, "keyterms": [], "language": "eng"})
    assert installed.dispatch(model="scribe_v1")["success"]
    form = dict(fields(installed.stub.calls[-1]))
    assert form["model_id"] == "scribe_v1"
    assert form["language_code"] == "eng"
    assert "no_verbatim" not in form and "keyterms" not in form


def test_keyterm_provider_maximum_and_boundaries(installed):
    installed.settings.update({"keyterms": [f"term {i}" for i in range(1000)], "max_keyterms": 1000})
    assert installed.dispatch()["success"]
    assert len([v for k, v in fields(installed.stub.calls[-1]) if k == "keyterms"]) == 1000
    installed.settings["keyterms"].append("one two three four five")
    assert "exceeds configured maximum" in installed.dispatch()["error"]
    installed.settings["keyterms"] = ["x" * 49, "one two three four five"]
    assert installed.dispatch()["success"]


@pytest.mark.parametrize("status,body,error,no_speech", [
    (422, {"detail": {"message": "invalid request"}}, "ElevenLabs STT API error (HTTP 422): invalid request", False),
    (403, {"error": "denied"}, "ElevenLabs STT API error (HTTP 403): denied", False),
    (500, b"x" * 400, "ElevenLabs STT API error (HTTP 500): " + "x" * 300, False),
    (200, {"text": "  "}, "ElevenLabs STT returned empty transcript", True),
    (200, {"error": "provider failed"}, "provider failed", False),
    (200, {"text": 42}, "Transcription response contained no text", False),
])
def test_response_errors_preserve_envelope(installed, status, body, error, no_speech):
    installed.stub.reply.update(status=status, body=body)
    result = installed.dispatch()
    assert result == {"success": False, "transcript": "", "provider": NAME, "error": error,
                      **({"no_speech": True} if no_speech else {})}


def test_invalid_json_and_asr_prefix(installed):
    installed.stub.reply["body"] = b"not json"
    assert "ElevenLabs STT transcription failed" in installed.dispatch()["error"]
    installed.stub.reply["body"] = {"text": "language en <asr_text> hello"}
    assert installed.dispatch()["transcript"] == "hello"


def test_timeout_argument_and_transport_failure(installed, monkeypatch):
    calls = []
    original = requests.adapters.HTTPAdapter.send

    def observe(adapter, request, **kwargs):
        calls.append(kwargs["timeout"])
        return original(adapter, request, **kwargs)

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", observe)
    assert installed.dispatch()["success"]
    assert calls == [120]

    def timeout(adapter, request, **kwargs):
        assert kwargs["timeout"] == 120
        raise requests.Timeout("synthetic timeout")

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", timeout)
    result = installed.dispatch()
    assert result["error"] == "ElevenLabs STT transcription failed: synthetic timeout"
    assert len(installed.stub.calls) == 1  # No implicit retry added.


def test_missing_audio_and_disabled_stt_do_not_upload(installed):
    installed.cfg["stt"]["enabled"] = False
    assert "disabled" in installed.dispatch()["error"]
    installed.cfg["stt"]["enabled"] = True
    installed.audio.unlink()
    assert "not found" in installed.dispatch()["error"].lower()
    assert not installed.stub.calls


def test_installed_pre_transcription_hook_overrides_model_and_language(installed):
    hook = installed.profile / "plugins" / "synthetic-hints"
    hook.mkdir()
    (hook / "plugin.yaml").write_text(
        "name: synthetic-hints\nversion: 1.0.0\ndescription: Test hints\n"
        "provides_hooks: [pre_transcription]\n", encoding="utf-8")
    (hook / "__init__.py").write_text(
        "def register(ctx):\n"
        "    ctx.register_hook('pre_transcription', lambda **kw: "
        "{'model': 'scribe_v1', 'language': 'nld'})\n", encoding="utf-8")
    installed.cfg["plugins"]["enabled"].append("synthetic-hints")
    installed.cfg["stt"]["language"] = "deu"
    installed.settings.update(language="eng", no_verbatim=False)
    assert installed.dispatch()["success"]
    form = dict(fields(installed.stub.calls[-1]))
    assert form["model_id"] == "scribe_v1"
    assert form["language_code"] == "nld"
    assert "no_verbatim" not in form


def test_v2_false_controls_are_sent_as_false(installed):
    installed.settings.update(no_verbatim="false", tag_audio_events="no", diarize="on")
    assert installed.dispatch()["success"]
    form = dict(fields(installed.stub.calls[-1]))
    assert form["no_verbatim"] == "false"
    assert form["tag_audio_events"] == "false"
    assert form["diarize"] == "true"
