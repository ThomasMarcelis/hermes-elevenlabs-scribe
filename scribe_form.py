"""Scribe multipart controls, extracted from the owned Hermes extension (MIT)."""

from pathlib import Path
from typing import Any


def truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return bool(value)


def normalize_keyterms(
    raw_terms: Any,
    *,
    max_keyterms: int = 95,
) -> list[str]:
    """Validate and de-duplicate Scribe keyterms while preserving order."""
    if raw_terms in (None, ""):
        return []
    if not isinstance(raw_terms, (list, tuple)):
        raise ValueError("ElevenLabs keyterms must be a list of strings")

    try:
        max_terms = int(max_keyterms)
    except (TypeError, ValueError) as exc:
        raise ValueError("ElevenLabs max_keyterms must be an integer") from exc
    if max_terms < 1 or max_terms > 1000:
        raise ValueError("ElevenLabs max_keyterms must be between 1 and 1000")

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_term in raw_terms:
        if not isinstance(raw_term, str):
            raise ValueError("ElevenLabs keyterms must be strings")
        term = raw_term.strip()
        if not term:
            continue
        if len(term) >= 50:
            raise ValueError(
                "ElevenLabs keyterms must contain fewer than 50 characters"
            )
        if len(term.split()) > 5:
            raise ValueError("ElevenLabs keyterms may contain at most 5 words")
        if any(
            char in term for char in ("[", "]", "{", "}", "<", ">", "\\")
        ):
            raise ValueError("ElevenLabs keyterm contains an unsupported character")
        identity = term.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append(term)

    if len(normalized) > max_terms:
        raise ValueError(
            "ElevenLabs keyterm count "
            f"{len(normalized)} exceeds configured maximum of {max_terms}"
        )
    return normalized


def load_keyterms(elevenlabs_config: dict[str, Any]) -> list[str]:
    """Load inline and optional absolute file-backed Scribe keyterms."""
    raw_terms = elevenlabs_config.get("keyterms") or []
    if not isinstance(raw_terms, (list, tuple)):
        raise ValueError("ElevenLabs keyterms must be a list of strings")
    combined = list(raw_terms)

    configured_path = str(elevenlabs_config.get("keyterms_file") or "").strip()
    if configured_path:
        keyterms_path = Path(configured_path).expanduser()
        if not keyterms_path.is_absolute():
            raise ValueError("ElevenLabs keyterms_file must be absolute")
        if not keyterms_path.is_file():
            raise ValueError("ElevenLabs keyterms_file does not exist")

        if keyterms_path.suffix.lower() in {".yaml", ".yml"}:
            try:
                import yaml
            except ImportError as exc:  # pragma: no cover - core dependency
                raise ValueError("YAML keyterms_file requires PyYAML") from exc
            loaded = yaml.safe_load(keyterms_path.read_text(encoding="utf-8"))
            if loaded is None:
                file_terms: Any = []
            elif isinstance(loaded, dict):
                file_terms = loaded.get("keyterms", [])
            else:
                file_terms = loaded
            if not isinstance(file_terms, (list, tuple)):
                raise ValueError(
                    "ElevenLabs YAML keyterms_file must contain a keyterms list"
                )
            combined.extend(file_terms)
        else:
            combined.extend(
                line.strip()
                for line in keyterms_path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            )

    return normalize_keyterms(
        combined,
        max_keyterms=elevenlabs_config.get("max_keyterms", 95),
    )


def build_form(
    model_name: str,
    elevenlabs_config: dict[str, Any],
) -> list[tuple[str, str]]:
    """Build allowlisted Scribe fields, retaining repeated keyterm entries."""
    form: list[tuple[str, str]] = [
        ("model_id", model_name),
        (
            "tag_audio_events",
            "true"
            if truthy(elevenlabs_config.get("tag_audio_events", False))
            else "false",
        ),
        (
            "diarize",
            "true"
            if truthy(elevenlabs_config.get("diarize", False))
            else "false",
        ),
    ]
    for name in ("language_code", "timestamps_granularity", "file_format"):
        value = elevenlabs_config.get(name)
        if value not in (None, ""):
            form.append((name, str(value)))

    is_scribe_v2 = model_name.strip().lower() == "scribe_v2"
    no_verbatim = truthy(elevenlabs_config.get("no_verbatim", False))
    keyterms = load_keyterms(elevenlabs_config)
    if not is_scribe_v2 and (no_verbatim or keyterms):
        raise ValueError(
            "ElevenLabs no_verbatim and keyterms require the scribe_v2 model"
        )

    if is_scribe_v2 and "no_verbatim" in elevenlabs_config:
        form.append(
            (
                "no_verbatim",
                "true" if no_verbatim else "false",
            )
        )

    num_speakers = elevenlabs_config.get("num_speakers")
    if num_speakers not in (None, ""):
        form.append(("num_speakers", str(int(num_speakers))))

    for keyterm in keyterms:
        form.append(("keyterms", keyterm))
    return form
