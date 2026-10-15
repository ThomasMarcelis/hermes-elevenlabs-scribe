"""Hermes-compatible REST response normalization, adapted from Hermes (MIT)."""

import re
from typing import Any

_ASR_TEXT_RE = re.compile(
    r"\s*language\s+[\w.-]+(?:\s*<audio_language>[^<]*</audio_language>)?\s*<asr_text>\s*(?P<text>.*)",
    flags=re.IGNORECASE | re.DOTALL)


class ResponseError(ValueError):
    """A structured response supplied an error or no usable text."""


def error_detail(body: dict[str, Any]) -> str:
    error = body.get("detail") or body.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error)
    return str(error) if error else ""


def extract_text(body: Any) -> str:
    if isinstance(body, str):
        text = body.strip()
    elif isinstance(body, dict):
        if not isinstance(body.get("text"), str):
            raise ResponseError(str(body.get("error") or "Transcription response contained no text"))
        text = body["text"].strip()
    else:
        text = str(body).strip()
    match = _ASR_TEXT_RE.match(text)
    return match.group("text").strip() if match else text
