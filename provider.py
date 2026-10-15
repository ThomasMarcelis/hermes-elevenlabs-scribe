"""ElevenLabs REST transcription through Hermes's native provider API (MIT)."""

import logging
from pathlib import Path
from typing import Any

import requests

from agent.transcription_provider import TranscriptionProvider
from hermes_cli.config import get_env_value, load_config

from .credentials import api_key
from .response import ResponseError, error_detail, extract_text
from .scribe_form import build_form, truthy

logger = logging.getLogger(__name__)
NAME = "elevenlabs-scribe"
BASE_URL = "https://api.elevenlabs.io/v1"


def failure(error: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "transcript": "", "provider": NAME, "error": error, **extra}


class ScribeProvider(TranscriptionProvider):
    @property
    def name(self) -> str:
        return NAME

    @property
    def display_name(self) -> str:
        return "ElevenLabs Scribe (extended controls)"

    def list_models(self) -> list[dict[str, str]]:
        return [{"id": "scribe_v2", "display": "Scribe v2"},
                {"id": "scribe_v1", "display": "Scribe v1 (no keyterms/no_verbatim)"}]

    def get_setup_schema(self) -> dict[str, Any]:
        return {"name": self.display_name, "badge": "cloud", "tag": "Scribe",
                "env_vars": [{"key": "ELEVENLABS_API_KEY", "prompt": "ElevenLabs API key",
                              "url": "https://elevenlabs.io/app/settings/api-keys"}]}

    def is_available(self) -> bool:
        try:
            return bool(api_key())
        except Exception:
            # A missing profile scope must never borrow launch-profile credentials.
            return False

    def transcribe(self, file_path: str, *, model: str | None = None,
                   language: str | None = None, **extra: Any) -> dict[str, Any]:
        key = ""
        try:
            key = api_key()
            if not key:
                return failure("ELEVENLABS_API_KEY not set")
            stt = load_config().get("stt") or {}
            cfg = stt.get(NAME) or {}
            if not isinstance(cfg, dict):
                raise ValueError(f"stt.{NAME} must be a mapping")
            model_name = model or cfg.get("model") or self.default_model()
            if not isinstance(model_name, str):
                raise ValueError("ElevenLabs model must be a string")
            data = build_form(model_name, cfg)
            if language:
                data = [item for item in data if item[0] != "language_code"]
                data.append(("language_code", language))
            elif cfg.get("language"):
                data = [item for item in data if item[0] != "language_code"]
                data.append(("language_code", cfg["language"]))
            base_url = str(cfg.get("base_url") or get_env_value("ELEVENLABS_STT_BASE_URL")
                           or BASE_URL).strip().rstrip("/")
            options = {}
            if "enable_logging" in cfg:
                options["params"] = {"enable_logging": truthy(cfg["enable_logging"])}
            if extra.get("prompt"):
                logger.debug("Scribe does not support transcription prompts; use keyterms.")
            with open(file_path, "rb") as audio:
                response = requests.post(
                    f"{base_url}/speech-to-text", headers={"xi-api-key": key},
                    files={"file": (Path(file_path).name, audio)}, data=data, timeout=120,
                    **options)
            if response.status_code != 200:
                try:
                    detail = error_detail(response.json()) or response.text[:300]
                except Exception:
                    detail = response.text[:300]
                return failure(f"ElevenLabs STT API error (HTTP {response.status_code}): "
                               + detail.replace(key, "[redacted]"))
            text = extract_text(response.json())
            if not text:
                return failure("ElevenLabs STT returned empty transcript", no_speech=True)
            logger.info("Transcribed %s via ElevenLabs Scribe (%s, %d chars)",
                        Path(file_path).name, model_name, len(text))
            return {"success": True, "transcript": text, "provider": NAME}
        except PermissionError:
            return failure(f"Permission denied: {file_path}")
        except ResponseError as exc:
            return failure(str(exc).replace(key, "[redacted]") if key else str(exc))
        except Exception as exc:
            detail = str(exc).replace(key, "[redacted]") if key else str(exc)
            logger.error("ElevenLabs STT transcription failed: %s", detail)
            return failure(f"ElevenLabs STT transcription failed: {detail}")
