"""Missing real host capabilities refuse admission and migration before side effects."""
import importlib.util
import sys
from types import SimpleNamespace

import pytest
from conftest import PLUGIN
from test_migration import migration


@pytest.mark.parametrize('missing', ['max_upload_bytes', 'cloud_preprocessing', 'language_config_aliases', 'is_source_suppressed'])
def test_missing_capability_refuses_registration_and_migration(tmp_path, monkeypatch, stub, capsys, missing):
    from agent.transcription_provider import TranscriptionProvider
    from hermes_cli import auth
    monkeypatch.delattr(auth if missing == 'is_source_suppressed' else TranscriptionProvider, missing)
    spec = importlib.util.spec_from_file_location('unsupported_scribe', PLUGIN / '__init__.py',
                                                submodule_search_locations=[str(PLUGIN)])
    plugin = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, plugin)
    spec.loader.exec_module(plugin)
    registered = []
    with pytest.raises(ValueError, match='unavailable' if missing == 'is_source_suppressed' else missing):
        plugin.register(SimpleNamespace(register_transcription_provider=registered.append))
    assert registered == []
    # No source exists: refusal must precede even reading configuration.
    output_dir = tmp_path / 'output'
    output_dir.mkdir()
    candidate = output_dir / 'candidate.yaml'
    with pytest.raises(SystemExit):
        migration.main(['--config', str(tmp_path / 'absent.yaml'), '--output', str(candidate),
                        '--accept-gateway-relay'])
    assert ("unavailable" if missing == "is_source_suppressed" else missing) in capsys.readouterr().err
    assert list(output_dir.iterdir()) == []
    assert not stub.calls
