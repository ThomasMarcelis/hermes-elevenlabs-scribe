"""Required public host capabilities for behavior-preserving Scribe migration."""


def require_host_capabilities() -> None:
    try:
        from agent.transcription_provider import TranscriptionProvider
    except ImportError as exc:
        raise ValueError("Run with the target Hermes interpreter; its transcription API is unavailable") from exc
    required = ("max_upload_bytes", "cloud_preprocessing")
    missing = [name for name in required if not hasattr(TranscriptionProvider, name)]
    if missing:
        raise ValueError(
            "ElevenLabs Scribe requires the Hermes public transcription audio-policy API "
            f"({', '.join(missing)} missing). Vanilla v0.22.2 is unsupported: "
            "upgrade to a host with this capability before installing or migrating; "
            "the original upload cap and cloud preprocessing must be preserved.")
