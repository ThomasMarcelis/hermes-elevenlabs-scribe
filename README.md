# Hermes ElevenLabs Scribe

Transcribe voice messages and audio files in Hermes with ElevenLabs Scribe, with your
own vocabulary (keyterms) and optional `no_verbatim` transcripts.

The plugin adds a speech-to-text provider called `elevenlabs-scribe`. Hermes'
built-in `elevenlabs` provider stays as it is. Scribe transcribes complete files;
it does not stream live partial transcripts.

## What you need

- **The paired Hermes host** at commit
  [`0d7c749`](https://github.com/ThomasMarcelis/hermes-agent/tree/0d7c749cff42cd4791e0342da226c6d499de5aeb).
  Stock Hermes v0.22.2 does not work. Set the host up as usual, including its
  operator-provisioned SQLite runtime.
- **An ElevenLabs API key.**
- **ffmpeg** (recommended), so Hermes can trim silence and convert or split large
  recordings.

## Install

Install the plugin in each profile that should use it. Replace `work` with your
profile name:

```bash
hermes -p work plugins install https://github.com/ThomasMarcelis/hermes-elevenlabs-scribe \
  --ref aa57a5d015a6a874753955bc31d7c2a1c2b88796 --yes-deps --enable
```

That commit is v0.1.0. `--ref` only accepts a full 40-character commit, not a tag.
`--yes-deps` lets Hermes install the Python dependencies (don't pip-install them
into the host yourself), and `--enable` turns the plugin on.

## Configure

Add your key to the profile's `.env` (a key in the profile's `elevenlabs` credential
pool also works):

```bash
ELEVENLABS_API_KEY=your-elevenlabs-key
```

Add this to the profile's `config.yaml`, keeping your other settings:

```yaml
stt:
  provider: elevenlabs-scribe
  elevenlabs-scribe:
    model: scribe_v2
```

Start a new session and send a voice message.

Language follows your Hermes settings (English by default). To choose another
language and help Scribe with names and jargon, extend the same block:

```yaml
stt:
  provider: elevenlabs-scribe
  elevenlabs-scribe:
    model: scribe_v2
    language: nl
    keyterms: [Hermes, Kubernetes, PostgreSQL]
```

## More

- [Configuration](docs/configuration.md): all options, language detection,
  vocabulary files, credentials, limits, privacy and troubleshooting.
- [Migrating from the extended built-in provider](docs/migration.md), for profiles
  that use `stt.provider: elevenlabs` on the earlier fork with keyterms and related
  controls.
- [Development](docs/development.md): offline tests.

MIT licensed. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
