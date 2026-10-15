"""Native Hermes transcription provider; no core modifications or import-time I/O."""


def register(ctx):
    from .provider import ScribeProvider

    ctx.register_transcription_provider(ScribeProvider())
