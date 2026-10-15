"""Synthetic profile credentials follow existing ElevenLabs resolution and isolation."""

import json

import pytest
from conftest import NAME


def test_dotenv_and_pool_fallback(installed, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    dotenv = installed.profile / ".env"
    dotenv.write_text("ELEVENLABS_API_KEY=synthetic-dotenv\n", encoding="utf-8")
    assert installed.dispatch()["success"]
    assert installed.stub.calls[-1]["key"] == "synthetic-dotenv"
    dotenv.unlink()
    from hermes_cli.config import invalidate_env_cache
    invalidate_env_cache()
    (installed.profile / "auth.json").write_text(json.dumps({"credential_pool": {
        "elevenlabs": [{"id": "fixture-key", "provider": "elevenlabs", "auth_type": "api_key",
                        "source": "manual", "access_token": "synthetic-pool", "priority": 0}]}}))
    assert installed.dispatch()["success"]
    assert installed.stub.calls[-1]["key"] == "synthetic-pool"


def test_suppression_and_missing_credentials_do_not_upload(installed, monkeypatch):
    from hermes_cli.auth import suppress_credential_source
    suppress_credential_source("elevenlabs", "env:ELEVENLABS_API_KEY")
    result = installed.dispatch()
    assert result["success"] is False and "not available" in result["error"]
    assert not installed.stub.calls
    from agent.transcription_registry import get_provider
    provider = get_provider(NAME)
    assert provider.transcribe(str(installed.audio))["error"] == "ELEVENLABS_API_KEY not set"
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    assert not provider.is_available()


def test_scoped_credentials_and_unscoped_multiplex_never_borrow(installed, caplog):
    from agent import secret_scope
    from agent.transcription_registry import get_provider
    assert installed.dispatch()["success"]
    provider = get_provider(NAME)
    secret_scope.set_multiplex_active(True)
    try:
        assert not provider.is_available()
        assert not provider.transcribe(str(installed.audio))["success"]
        assert "synthetic-test-key" not in caplog.text
        token = secret_scope.set_secret_scope({"ELEVENLABS_API_KEY": "synthetic-scope"},
                                               profile_home=str(installed.profile))
        try:
            assert provider.transcribe(str(installed.audio))["success"]
            assert installed.stub.calls[-1]["key"] == "synthetic-scope"
        finally:
            secret_scope.reset_secret_scope(token)
        token = secret_scope.set_secret_scope({}, profile_home=str(installed.home / "other"))
        try:
            assert not provider.is_available()
            assert provider.transcribe(str(installed.audio))["success"] is False
        finally:
            secret_scope.reset_secret_scope(token)
    finally:
        secret_scope.set_multiplex_active(False)


def test_error_responses_cannot_echo_key(installed, caplog):
    installed.stub.reply.update(status=401, body={"detail": "bad synthetic-test-key"})
    result = installed.dispatch()
    assert "synthetic-test-key" not in result["error"]
    assert "[redacted]" in result["error"]
    assert "synthetic-test-key" not in caplog.text


@pytest.mark.parametrize('pool_name', ['elevenlabs', 'custom:elevenlabs'])
def test_suppressed_environment_can_use_explicit_pool(installed, pool_name):
    from hermes_cli.auth import suppress_credential_source
    suppress_credential_source('elevenlabs', 'env:ELEVENLABS_API_KEY')
    auth = installed.profile / 'auth.json'
    data = json.loads(auth.read_text())
    data['credential_pool'] = {pool_name: [{'id': 'fixture', 'provider': pool_name,
        'auth_type': 'api_key', 'source': 'manual', 'access_token': 'synthetic-pool', 'priority': 0}]}
    auth.write_text(json.dumps(data))
    assert installed.dispatch()['success']
    assert installed.stub.calls[-1]['key'] == 'synthetic-pool'


def test_pool_failure_never_returns_or_logs_sensitive_detail(installed, monkeypatch, caplog):
    import sys

    from agent.transcription_registry import get_provider
    assert installed.dispatch()['success']
    provider = get_provider(NAME)
    credentials = sys.modules[type(provider).__module__.rsplit('.', 1)[0] + '.credentials']
    monkeypatch.delenv('ELEVENLABS_API_KEY')
    def fail(*args):
        raise RuntimeError('synthetic-private-store-value')
    monkeypatch.setattr(credentials, 'load_pool', fail)
    calls = len(installed.stub.calls)
    result = provider.transcribe(str(installed.audio))
    assert result['error'] == 'ELEVENLABS_API_KEY not set'
    assert not provider.is_available()
    assert len(installed.stub.calls) == calls
    assert 'synthetic-private-store-value' not in caplog.text
