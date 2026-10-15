"""Native Hermes transcription provider; no core modifications or import-time I/O."""


def register(ctx):
    from .host_api import require_host_capabilities

    require_host_capabilities()
    from .provider import ScribeProvider

    ctx.register_transcription_provider(ScribeProvider())
