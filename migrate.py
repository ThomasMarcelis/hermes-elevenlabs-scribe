#!/usr/bin/env python3
"""Preview a Scribe migration or create a NEW candidate; never edit the source."""

import argparse
import os
from copy import deepcopy
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

if __package__:
    from .host_api import require_host_capabilities
else:
    from host_api import require_host_capabilities

NAME = "elevenlabs-scribe"
CAVEATS = (
    "Required host audio-policy capabilities verified; original upload cap and cloud trim are preserved.",
    "Keep ELEVENLABS_API_KEY / ElevenLabs credential pools in the same profile.",
)


def migrated_config(original: dict) -> dict:
    """Copy all settings, keeping the original stanza for explicit rollback."""
    require_host_capabilities()
    if not isinstance(original, dict):
        raise ValueError("Configuration must be a YAML mapping")
    result = deepcopy(original)
    stt = result.get("stt")
    if not isinstance(stt, dict) or stt.get("provider") != "elevenlabs":
        raise ValueError("Migration requires explicit stt.provider: elevenlabs")
    if NAME in stt:
        raise ValueError("Destination STT stanza already exists; reconcile it manually")
    providers = stt.get("providers") or {}
    if not isinstance(providers, dict) or NAME in providers:
        raise ValueError("Conflicting stt.providers entry; reconcile it manually")
    cfg = deepcopy(stt.get("elevenlabs") or {})
    if not isinstance(cfg, dict):
        raise ValueError("stt.elevenlabs must be a mapping")
    # Hermes's plugin dispatcher reads model/language, not the built-in aliases.
    cfg["model"] = cfg.get("model_id", "scribe_v2")
    if not isinstance(cfg["model"], str) or not cfg["model"].strip():
        raise ValueError("Set a non-empty ElevenLabs model_id before migrating")
    language = next((v.strip() for v in (cfg.get("language"), cfg.get("language_code"))
                     if isinstance(v, str) and v.strip()), None)
    if language:
        cfg["language"] = language
    stt[NAME] = cfg
    stt["provider"] = NAME
    plugins = result.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        raise ValueError("plugins must be a mapping")
    enabled = plugins.setdefault("enabled", [])
    disabled = plugins.get("disabled") or []
    if not isinstance(enabled, list) or not isinstance(disabled, list):
        raise ValueError("plugins.enabled and plugins.disabled must be lists")
    if NAME in disabled:
        raise ValueError("Plugin is explicitly disabled; reconcile that setting first")
    if NAME not in enabled:
        enabled.append(NAME)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Absolute source config path")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Preview only (the default)")
    group.add_argument("--output", type=Path, help="Absolute NEW candidate path, never overwritten")
    args = parser.parse_args(argv)
    if not args.config.is_absolute() or (args.output and not args.output.is_absolute()):
        parser.error("All paths must be absolute")
    try:
        yaml = YAML()
        yaml.preserve_quotes = True
        with args.config.open(encoding="utf-8") as stream:
            candidate = migrated_config(yaml.load(stream))
        if args.output:
            # Exclusive create protects the input, existing files, and symlink targets.
            fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                yaml.dump(candidate, stream)
            print(f"Candidate written: {args.output}")
        else:
            print("Dry run: source unchanged; no candidate written.")
        print("Select stt.provider: elevenlabs-scribe; enable plugin: elevenlabs-scribe.")
        print("All existing Scribe settings are copied; model_id/language_code gain dispatcher aliases.")
        print("The original elevenlabs stanza and all unrelated settings remain intact.")
        for caveat in CAVEATS:
            print(f"Compatibility: {caveat}")
        return 0
    except YAMLError:
        parser.error("Cannot parse YAML configuration")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
