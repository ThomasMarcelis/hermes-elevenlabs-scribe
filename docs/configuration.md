# Configuration

Select the provider with `stt.provider: elevenlabs-scribe` and put its options
under `stt.elevenlabs-scribe` in the profile's `config.yaml`. Hermes' automatic
provider selection only picks built-in providers, so select this one explicitly.

| Option | Default | What it does |
|---|---|---|
| `model` | `scribe_v2` | `scribe_v2` or `scribe_v1`. `STT_ELEVENLABS_MODEL` changes the default. |
| `language` | inherited, usually `en` | Language code. See [Language](#language). |
| `keyterms` | none | Words and phrases to recognise. Needs `scribe_v2`. |
| `keyterms_file` | none | Absolute path to a YAML or TXT file of keyterms. |
| `max_keyterms` | `95` | Upper limit on keyterms per request, 1–1000. |
| `no_verbatim` | not sent | `true` asks for a non-verbatim transcript. Needs `scribe_v2`. |
| `diarize` | `false` | Label speakers. |
| `num_speakers` | not sent | Expected number of speakers. |
| `tag_audio_events` | `false` | Tag sounds such as laughter. |
| `timestamps_granularity`, `file_format` | not sent | Passed to ElevenLabs as given. |
| `enable_logging` | not sent | See [Privacy](#privacy). |
| `base_url` | `https://api.elevenlabs.io/v1` | Or `ELEVENLABS_STT_BASE_URL`. Receives your audio and key. |

`model_id` and `language_code` are accepted as aliases for `model` and `language`.
A model or language chosen for a single request by Hermes (for example by a hook)
overrides these settings.

## Language

If you set no language here, Scribe uses Hermes' global `stt.language`, which
defaults to `en`; if that is empty, it uses `HERMES_LOCAL_STT_LANGUAGE`. So it does
not auto-detect by default. For automatic detection:

- leave `language` and `language_code` unset here,
- set `stt.language: ""`, and
- unset `HERMES_LOCAL_STT_LANGUAGE`.

## Vocabulary

Inline `keyterms` and the `keyterms_file` are combined, and the file is reread on
every request. Each term must be shorter than 50 characters, at most five words,
and free of `[ ] { } < >` and backslashes. Duplicates are dropped, ignoring case.
An invalid term, a missing file or too many terms stops the request before any
audio is uploaded.

A YAML file holds a list, or a mapping with a `keyterms` list:

```yaml
keyterms:
  - Hermes
  - Kubernetes
```

A TXT file holds one term per line; blank lines and lines starting with `#` are
ignored. Transcription prompts are not supported; use keyterms instead.

## Credentials

The key is looked up on every request, in this order:

1. `ELEVENLABS_API_KEY` from the profile's `.env`;
2. the first entry in the profile's `elevenlabs` or `custom:elevenlabs` credential pool.

In a multi-profile gateway only the requesting profile's `ELEVENLABS_API_KEY` is
used. If that profile has no key, transcription is unavailable; it never borrows
another profile's key or a pool entry. If you have suppressed the environment key
in Hermes, it stays suppressed, but a separate pool entry can still be used outside
multi-profile mode.

## Uploads and limits

Hermes allows cloud uploads up to 5 GiB minus one byte; larger recordings are
re-encoded or split, which needs ffmpeg. ElevenLabs may apply its own limits.
Silence trimming is on by default; set `stt.cloud_trim_silence: false` to turn it
off. Each request times out after 120 seconds and is not retried. An empty
transcript is reported as no speech, and your key is removed from error messages.

## Privacy

Audio and the options above go to `base_url`. `enable_logging: false` asks
ElevenLabs for zero-retention mode, which
[ElevenLabs offers to enterprise customers only](https://elevenlabs.io/docs/api-reference/speech-to-text/convert).
It does not change what Hermes stores: logs, sessions, source recordings and
gateway files are unaffected.

## Troubleshooting

| Problem | Check |
|---|---|
| Provider not registered, or missing host capabilities | You are on the paired host, and the plugin is enabled in this profile. |
| Provider unavailable | This profile has a key, and the key isn't suppressed. |
| Scribe options ignored | `stt.provider` is set to `elevenlabs-scribe`. |
| A different handler runs | An `elevenlabs-scribe` command entry in `stt.providers` takes precedence; remove it. |
| "require the scribe_v2 model" or a keyterm error | The model (including any hook override) and your vocabulary. |
