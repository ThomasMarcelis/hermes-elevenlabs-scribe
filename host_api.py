"""Required public host capabilities for behavior-preserving Scribe migration."""


def require_host_capabilities() -> None:
    try:
        from agent.transcription_provider import TranscriptionProvider
        from hermes_cli.auth import is_source_suppressed
    except ImportError as exc:
        raise ValueError("Run with the target Hermes interpreter; its transcription API is unavailable") from exc
    required = ("max_upload_bytes", "cloud_preprocessing", "language_config_aliases")
    missing = [name for name in required if not hasattr(TranscriptionProvider, name)]
    if not callable(is_source_suppressed):
        missing.append("is_source_suppressed")
    if missing:
        raise ValueError(
            f"elevenlabs-scribe needs Hermes provider capabilities: {', '.join(missing)}. "
            "Vanilla v0.22.2 is unsupported; prepare a compatible host before migration.")
