# Hermes ElevenLabs Scribe

Native file transcription under **`elevenlabs-scribe`**, with Scribe v2 keyterms,
file-backed vocabulary, `no_verbatim` and logging controls. Uses normal Hermes
plugin dispatch; the built-in `elevenlabs` provider remains unchanged.

## Requirements

Hermes `>=0.22.2,<0.23` with the public `TranscriptionProvider.max_upload_bytes`,
`cloud_preprocessing`, and `language_config_aliases` capabilities and the public
`hermes_cli.auth.is_source_suppressed` helper. **Vanilla v0.22.2 is unsupported.**
Registration and migration refuse missing capabilities; version alone is insufficient.

Use [the paired host](https://github.com/ThomasMarcelis/hermes-agent/tree/0d7c749cff42cd4791e0342da226c6d499de5aeb) at commit
`0d7c749cff42cd4791e0342da226c6d499de5aeb` (`jd/thin-v0.22.2`).
The fork retains an operator-provisioned SQLite 3.53.4 runtime pin; provision
that host runtime first. Plugin source: [ThomasMarcelis/hermes-elevenlabs-scribe](https://github.com/ThomasMarcelis/hermes-elevenlabs-scribe).

An ElevenLabs key is required. ffmpeg enables Hermes's best-effort trimming and
large-file conversion/chunking. Tested on Linux with Python 3.14; host-isolated
plugin execution and other operating systems have not been exercised.

## Install in each intended profile

Use your installed Hermes launcher (`command -v hermes`), not an assumed virtualenv
layout. Replace the launcher path. `--ref` requires a full 40-character commit SHA,
not a tag; the pin below is the reviewed `v0.1.0` commit:

```bash
HERMES_CLI=/opt/hermes-bin/hermes
SCRIBE_SOURCE=https://github.com/ThomasMarcelis/hermes-elevenlabs-scribe
SCRIBE_REF=aa57a5d015a6a874753955bc31d7c2a1c2b88796
"$HERMES_CLI" -p work plugins install "$SCRIBE_SOURCE" --ref "$SCRIBE_REF" --yes-deps --enable
```

The Git installer records the selected commit. Hermes PM prepares bounded dependencies (`requests`, `PyYAML`,
`ruamel.yaml`); provisioning may need network access. Do not use raw pip in the host.

Set `ELEVENLABS_API_KEY` in the intended profile's `.env`, or reuse its `elevenlabs`
or `custom:elevenlabs` credential pool. Never put keys in this repository. Each
request resolves credentials anew. Multi-profile gateways use the requesting secret
scope only; an absent scope or key cannot borrow process credentials or pool keys.
A suppressed environment credential stays suppressed; a separate pool entry may
still be used outside multiplex mode.

## Configure

Merge this into the intended profile's configuration; `--enable` already enables the
plugin. No optional vocabulary file is needed:

```yaml
stt:
  provider: elevenlabs-scribe
  elevenlabs-scribe:
    model: scribe_v2
```

| Option in `stt.elevenlabs-scribe` | Default / behavior |
|---|---|
| `model` | `model_id` alias, then `STT_ELEVENLABS_MODEL`, then `scribe_v2`; explicit dispatch/hook model wins |
| `language` | `language_code` alias, then global `stt.language` (default `en`), then `HERMES_LOCAL_STT_LANGUAGE`; hook language wins |
| `keyterms`, `keyterms_file` | Empty; inline list followed by an absolute YAML/TXT file, read on each request |
| `max_keyterms` | 95; allowed range 1–1000 |
| `no_verbatim` | Omitted unless configured; true requires `scribe_v2` |
| `diarize`, `tag_audio_events` | false |
| `num_speakers`, `timestamps_granularity`, `file_format` | Optional multipart fields |
| `enable_logging` | Omitted; sent as a query parameter when configured |
| `base_url` | `ELEVENLABS_STT_BASE_URL`, then `https://api.elevenlabs.io/v1`; receives audio and key |

Omitting language **inherits English by default**, not auto-detection. For automatic
language detection, leave both provider language keys empty/absent, set global
`stt.language: ""`, and unset `HERMES_LOCAL_STT_LANGUAGE`.

Keyterms require `scribe_v2`. Terms are stripped, deduplicated case-insensitively in
first-seen order, and sent as repeated multipart fields. Each must be a string under
50 characters, at most five words, without `[ ] { } < >` or backslash. YAML accepts a
list or `keyterms` mapping; TXT accepts one term per line, ignoring blank/comment
lines. Missing or invalid files and excess terms fail before upload. Prompts are
unsupported; use keyterms.

Audio and fields go to the configured endpoint. Hermes retains its original upload
cap of **5 GiB minus one byte** and configurable cloud trimming
(`stt.cloud_trim_silence: false` disables it); larger recordings are re-encoded or
split. Requests use a 120-second timeout with no added retries. Empty transcripts
retain `no_speech`; response errors redact the API key. This cap preserves host
behavior, not a claim that the live API accepts every such file.

[ElevenLabs documents](https://elevenlabs.io/docs/api-reference/speech-to-text/convert)
`enable_logging=false` as zero-retention mode, with log/transcript storage features
unavailable, **enterprise customers only** (checked 2026-10-15). This setting controls
the vendor request, not Hermes logs, sessions, source recordings or gateway storage.
No live API or retention behavior is verified by the offline tests.

## Migrate safely from the extended built-in

This provider has **no streaming or live partial transcripts**. Migration refuses
`stt.streaming: true`. Keep the previous provider if streaming is required; disabling
it is a separate deliberate decision. Desktop audio also changes from a possible
direct vendor connection to **Desktop → Hermes gateway → ElevenLabs**. The helper
requires `--accept-gateway-relay`; do not pass it unless that data path is intended.

1. Prepare the compatible new host and plugin alongside the existing installation.
   Keep the running host/configuration unchanged. Copy the source configuration to
   a private staging directory and preserve any `STT_ELEVENLABS_MODEL` environment
   setting from the old process when invoking the helper.
2. Use the **new host's PM-managed interpreter** with isolated HOME/HERMES_HOME.
   These absolute example paths must point at your prepared artifacts:

```bash
SCRIBE_MIGRATION_HOME=$(mktemp -d /tmp/scribe-migration.XXXXXX)
env HOME="$SCRIBE_MIGRATION_HOME" HERMES_HOME="$SCRIBE_MIGRATION_HOME/profile" PYTHONPATH=/opt/new-hermes /opt/new-hermes-runtime/bin/python /opt/hermes-elevenlabs-scribe/migrate.py --config /srv/migration-input/config.yaml --accept-gateway-relay --dry-run
env HOME="$SCRIBE_MIGRATION_HOME" HERMES_HOME="$SCRIBE_MIGRATION_HOME/profile" PYTHONPATH=/opt/new-hermes /opt/new-hermes-runtime/bin/python /opt/hermes-elevenlabs-scribe/migrate.py --config /srv/migration-input/config.yaml --accept-gateway-relay --output /srv/migration-input/config.scribe-candidate.yaml
```

3. Review the candidate against the source. It normalizes legacy `model_id` (which
   wins over old `model`) and `language`/`language_code` (`language` wins) into active
   canonical keys. It preserves vocabulary, options, global settings, comments and
   the original `stt.elevenlabs` rollback stanza. No configuration values are printed.
4. Back up the current configuration and old host/plugin versions. At an authorized
   cutover between sessions, install/enable the pinned plugin in the target profile,
   deploy the compatible host and reviewed candidate **together**, then start the next
   session. Never run the restored built-in with extended controls during an interim
   upgrade. The helper does not install, activate, replace live config or restart.

Candidates are complete, exclusive 0600 files; existing files/symlinks are refused.
Failed serialization/publication leaves no partial candidate. Destination stanzas,
command conflicts or disabled plugins require reconciliation. Rollback restores the
previous host and source configuration together: selecting `elevenlabs` on the new
host alone does not restore the extended controls.

## Troubleshooting

| Symptom | Action |
|---|---|
| No provider registered / missing capabilities | Check host requirements and plugin enablement in this profile |
| Plugin not available | Check this profile's key, scope and suppression settings |
| Controls ignored | Explicitly select `elevenlabs-scribe`; auto-selection still uses built-ins |
| Wrong handler | A same-name command entry in `stt.providers` takes precedence |
| Scribe v2 required / keyterm file or limit error | Check model/hook settings and vocabulary |

## Development

Requirements: a compatible Hermes source checkout, an interpreter with **pytest and
host/plugin dependencies**, **ffmpeg on PATH**, and **loopback sockets**. Set
`HERMES_SOURCE`, `SCRIBE_SOURCE`, and `HERMES_TEST_PYTHON` to their absolute paths.
Run this exact block from any directory; it uses synthetic audio/keys and only loopback
HTTP, including real installed-directory discovery and multipart assertions:

```bash
: "${HERMES_SOURCE:?Set the absolute compatible Hermes checkout path}"
: "${SCRIBE_SOURCE:?Set the absolute plugin checkout path}"
: "${HERMES_TEST_PYTHON:?Set the absolute prepared test interpreter path}"
SCRIBE_TEST_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/scribe-tests.XXXXXX")
mkdir -p "$SCRIBE_TEST_ROOT/home" "$SCRIBE_TEST_ROOT/profile"
env HOME="$SCRIBE_TEST_ROOT/home" HERMES_HOME="$SCRIBE_TEST_ROOT/profile" HERMES_PYTHON="$HERMES_TEST_PYTHON" bash "$HERMES_SOURCE/scripts/run_tests.sh" "$SCRIBE_SOURCE/tests" --file-retries 0 -- --hermes-source "$HERMES_SOURCE"
```

The canonical runner sanitizes environment variables, including PYTHONPATH and
HERMES_HOME; temporary HOME prevents live-profile access and each fixture binds its
own profile. `--hermes-source` explicitly selects and asserts core import origins.
For native admission, run `"$HERMES_CLI" plugins validate "$SCRIBE_SOURCE"`.

MIT licensed; see LICENSE and NOTICE for upstream and extension attribution.
