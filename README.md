# Hermes ElevenLabs Scribe

A standalone native Hermes transcription provider named **`elevenlabs-scribe`**.
It retains the owned Scribe controls without replacing Hermes's built-in
`elevenlabs` provider. Registration uses `TranscriptionProvider` and
`ctx.register_transcription_provider()`; audio uses normal `transcribe_audio()`
dispatch. It does not patch Hermes modules or register model tools.

Tested with Hermes **v0.22.2**, Python 3.14, on Linux. The manifest restricts
compatibility to `>=0.22.2,<0.23`; revalidate before widening it. This is a
file-transcription provider, not a streaming provider. It is independent of
and not endorsed by ElevenLabs or Nous Research.

## Installation

Use the same profile and PM-managed Hermes interpreter as your agent. The
following absolute paths are generic examples: replace `/opt/hermes` with your
Hermes checkout/runtime and `/opt/hermes-elevenlabs-scribe` with this repository.
No hosted repository or catalog entry is assumed.

```bash
/opt/hermes/.venv/bin/hermes plugins validate /opt/hermes-elevenlabs-scribe
/opt/hermes/.venv/bin/hermes plugins install file:///opt/hermes-elevenlabs-scribe --yes-deps --enable
```

Hermes's native directory layout is also supported: place this repository at
`/srv/hermes-profile/plugins/elevenlabs-scribe` (with the manifest and registration
module at that directory's root), prepare declared dependencies through Hermes
PM, and add `elevenlabs-scribe` to `plugins.enabled` for that profile. The offline
integration tests exercise this installed-directory discovery path.

Dependencies are declared in the native manifest, with upper bounds:
`requests>=2.33.0,<3`, `PyYAML>=6.0.3,<7`, and `ruamel.yaml>=0.18.16,<0.20`.
Do not install them into a shared Hermes environment with raw pip. No ElevenLabs
SDK, model download, or model inference is required to install or test.

Set `ELEVENLABS_API_KEY` through Hermes's credential setup in the target profile.
Existing profile dotenv credentials and `elevenlabs` / `custom:elevenlabs`
credential pools remain usable; credentials are resolved per call, not captured
at registration. Multiplexed scopes are authoritative, including an absent key.
Environment credentials suppressed by Hermes authentication remain suppressed.

```yaml
plugins:
  enabled: [elevenlabs-scribe]  # append to any existing list
stt:
  provider: elevenlabs-scribe
  elevenlabs-scribe:
    model: scribe_v2
    language: eng             # omit or leave empty to auto-detect
    tag_audio_events: false
    diarize: false
    no_verbatim: false
    keyterms: [Quartz, Example Labs]
    keyterms_file: /srv/hermes-profile/vocabulary.yaml
    max_keyterms: 95
    enable_logging: false    # optional; omitted means provider default
```

Keep secrets out of the configuration examples. `base_url` optionally replaces
`https://api.elevenlabs.io/v1`; it receives the API key and audio, so choose a
trusted endpoint. The legacy `ELEVENLABS_STT_BASE_URL` fallback remains supported.
`timestamps_granularity`, `num_speakers`, and `file_format` are optional multipart
controls. `enable_logging` is a query parameter and is never a multipart field;
it controls the provider's logging, not Hermes's logs. This plugin adds no
telemetry or local audio/transcript retention.

## Keyterms and model gates

Inline terms are followed by file terms. Whitespace is stripped, empty terms
are omitted, and duplicates are removed case-insensitively while preserving the
first spelling and order. Each term is a separate multipart `keyterms` field.
A YAML file accepts a list or a mapping with a `keyterms` list; a TXT file accepts
one term per line and ignores blank lines and lines beginning with `#`.
The file path must be absolute (home expansion remains supported); files are
read afresh for each transcription. Missing, unreadable, or malformed files fail
the request instead of dropping vocabulary hints.

Terms must be strings, shorter than 50 characters, at most five words, and may
not contain `[`, `]`, `{`, `}`, `<`, `>`, or `\`. The default cap is 95 unique
terms; `max_keyterms` may be 1–1000. Exceeding the cap fails without uploading.
`no_verbatim: true` and nonempty keyterms require `scribe_v2`. With `scribe_v1`,
false `no_verbatim` and empty keyterms are omitted. Prompts are unsupported,
as in the built-in Scribe backend; use keyterms for vocabulary hints.

A request has a 120-second Requests timeout and no added retries. Existing
non-200 error details, empty-transcript `no_speech`, malformed JSON/text errors,
and permission-error envelopes are preserved. The provider field is now
`elevenlabs-scribe`. An echoed API key in an error is redacted before returning
or logging it.

## Migration from the owned built-in extension

Do this before switching to a core build that restores upstream `elevenlabs`.
The upstream built-in ignores the owned keyterm/no-verbatim/logging extensions.
Installing this plugin alone does **not** select it. Do not keep
`stt.provider: elevenlabs` if those controls are required.

The helper defaults to a dry run and prints only the migration actions and
compatibility caveats, not configuration values, keyterms, or credentials:

```bash
/opt/hermes/.venv/bin/python /opt/hermes-elevenlabs-scribe/migrate.py --config /srv/hermes-profile/config.yaml --dry-run
/opt/hermes/.venv/bin/python /opt/hermes-elevenlabs-scribe/migrate.py --config /srv/hermes-profile/config.yaml --output /srv/hermes-profile/config.scribe-candidate.yaml
```

It requires an explicitly selected `elevenlabs` provider, copies the entire
`stt.elevenlabs` mapping to `stt.elevenlabs-scribe`, adds the plugin to the enabled
list, and changes the provider name. Every keyterm, file path, cap,
`no_verbatim`, logging flag, and other option is retained. `model_id` also becomes
`model` (default `scribe_v2` if omitted); the effective provider `language` or
`language_code` also becomes `language`. These aliases matter because Hermes's
plugin dispatcher reads `model` and `language`, and a global language hint must
not displace the old provider-specific `language_code`. For new configurations,
use the canonical `model` and `language` keys shown above.

The old stanza, unrelated configuration, YAML comments, and quoting remain.
Candidates are created exclusively with mode 0600. The helper never overwrites
an existing destination, follows a destination symlink, changes the source,
installs the plugin, or activates/restarts a runtime. Existing destination
stanzas, conflicting command-provider entries, disabled plugins, or malformed
configuration require manual reconciliation. Review the candidate, prepare the
plugin, then deploy the configuration through your normal controlled workflow
for the next session. Rollback requires explicitly selecting `elevenlabs` again;
the retained old stanza supports rollback to the former owned core build.

### Host compatibility caveats

- Hermes v0.22.2 applies its **25 MiB** plugin upload cap. Larger inputs go through
  core re-encoding/chunking, and fail if they cannot be made to fit. The built-in
  ElevenLabs route has a vendor-specific cap just below 5 GiB. Large-file
  behavior is consequently different and needs acceptance before migration.
- Hermes skips its built-in cloud silence trimming for plugin providers. Original
  audio reaches this plugin unless the generic preprocessing/chunking path needs
  a conversion. The cloud trim settings remain in configuration for other
  providers. This can change uploaded duration, cost, and pause handling.
- Explicit selection is required; automatic provider detection continues to
  select the built-in. A command provider with the same name takes precedence.
- Missing credentials use Hermes's standard plugin-unavailable error at dispatch;
  a direct provider call retains `ELEVENLABS_API_KEY not set`.
- One compatibility exception is retained: the non-underscored
  `hermes_cli.auth.is_source_suppressed` helper preserves the built-in credential
  suppression behavior. Hermes's admission lint flags it as outside the documented
  plugin API. No private transcription implementation is imported, and there is
  no runtime rebinding. Keep the version bound and revalidate this helper during
  upgrades; a documented credential-suppression API would remove this exception.

## Offline verification

Use Hermes's canonical runner with a prepared test interpreter. The example
creates temporary HOME and HERMES_HOME, then the fixtures create a separate
profile per test and copy the native plugin into that profile. Run from the
Hermes source checkout so source imports outrank an unrelated editable install:

```bash
cd /opt/hermes
SCRIBE_TEST_HOME=$(mktemp -d /var/tmp/scribe-test-home.XXXXXX)
env HOME="$SCRIBE_TEST_HOME" HERMES_HOME="$SCRIBE_TEST_HOME/profile" HERMES_PYTHON=/opt/hermes-test/bin/python bash /opt/hermes/scripts/run_tests.sh /opt/hermes-elevenlabs-scribe/tests --file-retries 0
```

The tests use synthetic WAV audio, synthetic keys, and a loopback HTTP server.
They assert real installed discovery, exact repeated multipart wire fields and
query parameters, model gates, validation limits, migration, credential scopes,
response errors, timeout handling, and unchanged built-in dispatch. They never
call a model or an external transcription service. Network-restricted runners
must allow loopback sockets (a private network namespace is suitable).

MIT licensed. See the repository's license and attribution notice.
