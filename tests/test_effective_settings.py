"""Configuration aliases and inherited hints reach real multipart dispatch."""
import pytest
from conftest import fields


@pytest.mark.parametrize('settings,global_language,env_language,expected', [
    ({}, None, None, 'en'),
    ({'language_code': 'spa'}, 'fr', None, 'spa'),
    ({'language': 'nld', 'language_code': 'spa'}, 'fr', None, 'nld'),
    ({'language': '', 'language_code': 'spa'}, 'fr', None, 'spa'),
    ({}, '', 'deu', 'deu'),
    ({'language': '', 'language_code': ''}, '', None, None),
])
def test_effective_language(installed, monkeypatch, settings, global_language, env_language, expected):
    installed.settings.update(settings)
    if global_language is not None:
        installed.cfg['stt']['language'] = global_language
    if env_language is not None:
        monkeypatch.setenv('HERMES_LOCAL_STT_LANGUAGE', env_language)
    assert installed.dispatch()['success']
    assert dict(fields(installed.stub.calls[-1])).get('language_code') == expected


def test_legacy_model_alias_and_environment_default(installed, monkeypatch):
    installed.settings.pop('model')
    installed.settings['model_id'] = 'scribe_v1'
    assert installed.dispatch()['success']
    assert dict(fields(installed.stub.calls[-1]))['model_id'] == 'scribe_v1'
    installed.settings.pop('model_id')
    monkeypatch.setenv('STT_ELEVENLABS_MODEL', 'scribe_v1')
    assert installed.dispatch()['success']
    assert dict(fields(installed.stub.calls[-1]))['model_id'] == 'scribe_v1'


def test_minimal_config_and_base_url_environment(installed, monkeypatch):
    installed.cfg['stt'] = {'provider': 'elevenlabs-scribe'}
    monkeypatch.setenv('ELEVENLABS_STT_BASE_URL', installed.stub.url)
    assert installed.dispatch()['success']
    assert dict(fields(installed.stub.calls[-1]))['model_id'] == 'scribe_v2'


def test_hook_hints_override_both_language_aliases_and_model(installed):
    hook = installed.profile / 'plugins' / 'synthetic-hints'
    hook.mkdir()
    (hook / 'plugin.yaml').write_text('name: synthetic-hints\nversion: 1.0.0\nprovides_hooks: [pre_transcription]\n')
    (hook / '__init__.py').write_text(
        'def hints(**kwargs):\n    return {"language": "deu", "model": "scribe_v1"}\n'
        'def register(ctx):\n    ctx.register_hook("pre_transcription", hints)\n')
    installed.cfg['plugins']['enabled'].append('synthetic-hints')
    installed.settings.update(language='nld', language_code='spa')
    assert installed.dispatch()['success']
    form = dict(fields(installed.stub.calls[-1]))
    assert form['language_code'] == 'deu' and form['model_id'] == 'scribe_v1'


@pytest.mark.parametrize('settings,env_model,model,language', [
    ({'model': 'ignored-old-model', 'model_id': 'scribe_v1',
      'language': 'nld', 'language_code': 'spa'}, 'scribe_v2', 'scribe_v1', 'nld'),
    ({'model': 'ignored-old-model', 'language_code': 'spa'}, 'scribe_v1', 'scribe_v1', 'spa'),
])
def test_migrated_effective_aliases_reach_wire(installed, monkeypatch, settings, env_model, model, language):
    from test_migration import migration
    monkeypatch.setenv('STT_ELEVENLABS_MODEL', env_model)
    settings = {**settings, 'base_url': installed.stub.url}
    cfg = {'stt': {'provider': 'elevenlabs', 'language': 'fr', 'elevenlabs': settings,
                   'cloud_trim_silence': False}}
    candidate = migration.migrated_config(cfg, accept_gateway_relay=True)
    assert candidate['stt']['elevenlabs'] == settings
    active = candidate['stt']['elevenlabs-scribe']
    assert 'model_id' not in active and 'language_code' not in active
    installed.cfg.clear()
    installed.cfg.update(candidate)
    assert installed.dispatch()['success']
    form = dict(fields(installed.stub.calls[-1]))
    assert form['model_id'] == model and form['language_code'] == language


def test_desktop_file_plugin_uses_gateway_relay(installed):
    from tools.voice_client_config import _resolve_stt_client_config
    installed.cfg['stt']['provider'] = 'elevenlabs'
    installed.write_config()
    direct = _resolve_stt_client_config()
    assert direct['mode'] == 'direct' and direct['wire'] == 'elevenlabs-stt'
    installed.cfg['stt']['provider'] = 'elevenlabs-scribe'
    installed.write_config()
    assert _resolve_stt_client_config() == {'mode': 'relay', 'reason': 'command/plugin provider'}
    assert not installed.stub.calls
