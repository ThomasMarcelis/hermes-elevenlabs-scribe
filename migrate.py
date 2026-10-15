#!/usr/bin/env python3
"""Preview a Scribe migration or create a NEW candidate; never edit the source."""

import argparse
import os
from copy import deepcopy
from pathlib import Path
from tempfile import NamedTemporaryFile

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

if __package__:
    from .host_api import require_host_capabilities
    from .scribe_form import truthy
else:
    from host_api import require_host_capabilities
    from scribe_form import truthy

NAME = "elevenlabs-scribe"


def migrated_config(original: dict, *, accept_gateway_relay: bool = False) -> dict:
    """Copy all settings, keeping the original stanza for explicit rollback."""
    require_host_capabilities()
    if not isinstance(original, dict):
        raise ValueError("Configuration must be a YAML mapping")
    result = deepcopy(original)
    stt = result.get("stt")
    if not isinstance(stt, dict) or stt.get("provider") != "elevenlabs":
        raise ValueError("Migration requires explicit stt.provider: elevenlabs")
    if truthy(stt.get("streaming", False)):
        raise ValueError("stt.streaming is enabled: this provider has no live partial transcripts. "
                         "Migration refused; keep the streaming provider or deliberately disable "
                         "streaming in the source copy before migration.")
    if not accept_gateway_relay:
        raise ValueError("Desktop audio will pass through the Hermes gateway instead of going "
                         "directly to ElevenLabs. Use --accept-gateway-relay only if this is intended.")
    if NAME in stt:
        raise ValueError("Destination STT stanza already exists; reconcile it manually")
    providers = stt.get("providers") or {}
    if not isinstance(providers, dict) or NAME in providers:
        raise ValueError("Conflicting stt.providers entry; reconcile it manually")
    cfg = deepcopy(stt.get("elevenlabs") or {})
    if not isinstance(cfg, dict):
        raise ValueError("stt.elevenlabs must be a mapping")
    # Hermes's plugin dispatcher reads model/language, not the built-in aliases.
    cfg["model"] = cfg.pop("model_id", os.getenv("STT_ELEVENLABS_MODEL", "scribe_v2"))
    if not isinstance(cfg["model"], str) or not cfg["model"].strip():
        raise ValueError("Set a non-empty ElevenLabs model_id before migrating")
    language = next((v.strip() for v in (cfg.get("language"), cfg.get("language_code"))
                     if isinstance(v, str) and v.strip()), None)
    cfg.pop("language_code", None)
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


def write_candidate(yaml: YAML, candidate: dict, output: Path) -> None:
    """Publish a complete 0600 candidate without replacing any existing entry."""
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                            prefix=f".{output.name}.") as staged:
        yaml.dump(candidate, staged)
        staged.flush()
        os.fsync(staged.fileno())
        # Same-directory hard link is atomic and refuses files and symlinks alike.
        os.link(staged.name, output)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Absolute source config path")
    parser.add_argument("--accept-gateway-relay", action="store_true",
                        help="Deliberately accept Desktop audio passing through the Hermes gateway")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Preview only (the default)")
    group.add_argument("--output", type=Path, help="Absolute NEW candidate path, never overwritten")
    args = parser.parse_args(argv)
    if not args.config.is_absolute() or (args.output and not args.output.is_absolute()):
        parser.error("All paths must be absolute")
    try:
        require_host_capabilities()
        yaml = YAML()
        yaml.preserve_quotes = True
        with args.config.open(encoding="utf-8") as stream:
            candidate = migrated_config(yaml.load(stream), accept_gateway_relay=args.accept_gateway_relay)
        if args.output:
            write_candidate(yaml, candidate, args.output)
            print(f"Candidate written: {args.output}")
        else:
            print("Dry run: source unchanged; no candidate written.")
        print("Would select elevenlabs-scribe and enable it; model/language aliases are normalized.")
        print("Desktop audio uses the gateway relay. Source and rollback stanza stay unchanged.")
        print("Next: review the candidate and coordinate host, plugin and config cutover together.")
        return 0
    except YAMLError:
        parser.error("Cannot parse YAML configuration")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
