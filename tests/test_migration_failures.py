"""Candidate publication is all-or-nothing and data-path changes require consent."""
import pytest
import yaml
from test_migration import migration


def source_config(tmp_path):
    source = tmp_path / 'source.yaml'
    source.write_text('stt:\n  provider: elevenlabs\n  elevenlabs: {}\n')
    return source


def test_environment_model_survives_migration(monkeypatch):
    monkeypatch.setenv('STT_ELEVENLABS_MODEL', 'scribe_v1')
    cfg = migration.migrated_config({'stt': {'provider': 'elevenlabs', 'elevenlabs': {}}}, accept_gateway_relay=True)
    assert cfg['stt']['elevenlabs-scribe']['model'] == 'scribe_v1'


def test_failed_yaml_write_leaves_no_candidate(tmp_path, monkeypatch):
    source = source_config(tmp_path)
    before = source.read_bytes()
    candidate = tmp_path / 'candidate.yaml'
    def fail(self, data, stream):
        stream.write('partial:')
        raise OSError('synthetic write failure')
    monkeypatch.setattr(migration.YAML, 'dump', fail)
    with pytest.raises(SystemExit):
        migration.main(['--config', str(source), '--output', str(candidate), '--accept-gateway-relay'])
    assert not candidate.exists()
    assert source.read_bytes() == before


def test_symlink_output_refused(tmp_path):
    source = source_config(tmp_path)
    candidate = tmp_path / 'candidate.yaml'
    candidate.symlink_to(source)
    before = source.read_bytes()
    with pytest.raises(SystemExit):
        migration.main(['--config', str(source), '--output', str(candidate), '--accept-gateway-relay'])
    assert candidate.is_symlink() and source.read_bytes() == before


@pytest.mark.parametrize('streaming', [False, True])
def test_migration_needs_deliberate_data_path_decision(tmp_path, streaming):
    source = source_config(tmp_path)
    cfg = yaml.safe_load(source.read_text())
    cfg['stt']['streaming'] = streaming
    source.write_text(yaml.safe_dump(cfg))
    candidate = tmp_path / 'candidate.yaml'
    with pytest.raises(SystemExit):
        migration.main(['--config', str(source), '--output', str(candidate)])
    assert not candidate.exists()


def test_streaming_refused_even_with_relay_consent(tmp_path):
    source = source_config(tmp_path)
    source.write_text('stt:\n  provider: elevenlabs\n  streaming: true\n')
    candidate = tmp_path / 'candidate.yaml'
    with pytest.raises(SystemExit):
        migration.main(['--config', str(source), '--output', str(candidate), '--accept-gateway-relay'])
    assert not candidate.exists()


def test_failed_publication_leaves_no_candidate_or_staging_file(tmp_path, monkeypatch):
    source = source_config(tmp_path)
    before = source.read_bytes()
    output_dir = tmp_path / 'output'
    output_dir.mkdir()
    candidate = output_dir / 'candidate.yaml'
    def fail(*args):
        raise OSError('synthetic publication failure')
    monkeypatch.setattr(migration.os, 'link', fail)
    with pytest.raises(SystemExit):
        migration.main(['--config', str(source), '--output', str(candidate), '--accept-gateway-relay'])
    assert list(output_dir.iterdir()) == []
    assert source.read_bytes() == before
