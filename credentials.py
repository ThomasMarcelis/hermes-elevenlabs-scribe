"""Resolve the existing ElevenLabs credential without retaining it on the provider."""

from agent.credential_pool import load_pool
from agent.secret_scope import get_secret, is_multiplex_active
from hermes_cli.auth import is_source_suppressed
from hermes_cli.config import get_env_value


def api_key() -> str:
    suppressed = is_source_suppressed("elevenlabs", "env:ELEVENLABS_API_KEY")
    if not suppressed:
        key = (get_secret("ELEVENLABS_API_KEY", "") or "").strip()
        if key:
            return key
    # Deliberately stricter than the built-in raw-env fallback: a multiplex scope is authoritative,
    # including a miss. Never fall back to a pool or another profile's dotenv.
    if is_multiplex_active():
        return ""
    if not suppressed:
        key = (get_env_value("ELEVENLABS_API_KEY") or "").strip()
        if key:
            return key
    try:
        for name in ("elevenlabs", "custom:elevenlabs"):
            pool = load_pool(name)
            entry = pool.peek() if pool.has_credentials() else None
            key = str(getattr(entry, "runtime_api_key", "")
                      or getattr(entry, "access_token", "") or "").strip()
            if key:
                return key
    except Exception:
        # Pool failures may contain sensitive store contents. Fail closed without echoing them.
        return ""
    return ""
