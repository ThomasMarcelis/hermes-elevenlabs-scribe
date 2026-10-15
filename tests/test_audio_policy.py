"""Real installed Scribe requests retain the original host audio policy."""

import math
import struct
import wave

import pytest
from conftest import NAME


@pytest.mark.parametrize("trim", [True, False])
def test_original_cap_and_cloud_preprocessing_reach_http(installed, trim):
    from agent.transcription_registry import get_provider
    from tools.transcription_chunking import upload_limit

    tone = b"".join(struct.pack("<h", int(8000 * math.sin(i * math.tau * 440 / 16000)))
                    for i in range(16000))
    with wave.open(str(installed.audio), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes((tone + b"\0\0" * 16000) * 10)
    original = installed.audio.read_bytes()
    installed.cfg["stt"]["cloud_trim_silence"] = trim
    result = installed.dispatch()
    assert result["success"], result
    provider = get_provider(NAME)
    assert provider.max_upload_bytes == upload_limit("elevenlabs", "scribe_v2")[0] == 5_368_709_119
    assert provider.cloud_preprocessing is True
    uploads = [part for part in installed.stub.calls[-1]["parts"] if part[0] == "file"]
    assert len(uploads) == 1
    _field, filename, data = uploads[0]
    if trim:
        assert filename.endswith("-trimmed.m4a")
        assert data != original and len(data) < len(original)
    else:
        assert filename == installed.audio.name and data == original
    assert installed.audio.read_bytes() == original
